import argparse
import asyncio
import math
import time

from loguru import logger

from crawler.engine.crawler_engine import CrawlerEngine
from crawler.models.contract import CrawlResult
from crawler.services.database import session_local
from crawler.services.request_manager import RequestManager
from crawler.services.ticker_service import TickerService
from crawler.spiders.b3_spider import B3Spider
from crawler.spiders.fundamentus_spider import FundamentusSpider
from crawler.spiders.statusinvest_spider import StatusInvestSpider
from crawler.tasks import crawl_macro_data_task

# Increased concurrency for enrichment tasks within a batch
enrichment_semaphore = asyncio.Semaphore(15)


async def safe_enrich_ticker(symbol: str, engine: CrawlerEngine, company_exists: bool, results_dict: dict):
    """
    Safely enriches a single ticker using a semaphore to control concurrency.
    """
    async with enrichment_semaphore:
        try:
            result = results_dict.get(symbol) or CrawlResult(symbol=symbol)
            
            # First Fallback: Fundamentus (only if really needed)
            if not result.is_complete():
                await engine.fundamentus_spider.enrich_async(result)

            # Second Fallback: StatusInvest (Conditional metadata enrichment)
            if not result.is_complete() or not company_exists:
                await engine.status_spider.crawl_ticker_async(
                    result.symbol, enrich_metadata=not company_exists
                )

            engine._calculate_advanced_metrics(result)

            # Persistence (Still wrapped in thread as it's synchronous SQLAlchemy)
            await asyncio.to_thread(engine._save_to_db, result)
        except Exception as e:
            logger.error(f"Failed to enrich/save {symbol}: {e}")


async def process_sub_batch_parallel(sub_batch: list[str], engine: CrawlerEngine, data_service):
    """
    Processes a sub-batch by fetching prices in bulk and then enriching tickers in parallel.
    """
    # 1. Batch Primary Source: B3 (yfinance batch) - One network call
    results_dict = await engine.b3_spider.crawl_batch_async(sub_batch)

    # 2. Bulk-check which companies already exist (single DB round-trip per sub-batch)
    existing_symbols = await asyncio.to_thread(data_service.get_existing_symbols, sub_batch)

    # 3. Parallel Enrichment and Persistence
    tasks = [
        safe_enrich_ticker(symbol, engine, symbol in existing_symbols, results_dict)
        for symbol in sub_batch
    ]
    await asyncio.gather(*tasks)


async def crawl_tickers_async(tickers: list[str]):
    """
    Orchestrates the asynchronous crawling of a list of tickers using optimized batching.
    """
    request_manager = RequestManager()
    db = session_local()
    
    # Pre-initialize spiders to share them (and their caches) across tasks
    spiders = {
        "b3": B3Spider(),
        "fundamentus": FundamentusSpider(request_manager),
        "status": StatusInvestSpider(request_manager),
    }
    
    try:
        engine = CrawlerEngine(db, request_manager=request_manager, spiders=spiders)
        
        # Increased sub-batch size for yfinance efficiency
        sub_batch_size = 100
        for i in range(0, len(tickers), sub_batch_size):
            sub_batch = tickers[i : i + sub_batch_size]
            logger.info(f"Main: Processing sub-batch {i//sub_batch_size + 1} ({len(sub_batch)} tickers)")
            await process_sub_batch_parallel(sub_batch, engine, engine.data_service)
            
    finally:
        await request_manager.close()
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Stock Market Crawler")
    parser.add_argument("--chunk", type=int, default=0, help="Chunk index (0-based)")
    parser.add_argument("--total-chunks", type=int, default=1, help="Total number of chunks")
    args = parser.parse_args()

    logger.info(f"Starting stock-market-crawler (Optimized Batch Mode) - Chunk {args.chunk}/{args.total_chunks}...")

    # 1. Fetch Macro Data (only on the first chunk to avoid redundancy)
    if args.chunk == 0:
        try:
            crawl_macro_data_task()
        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")

    # 2. Fetch Tickers
    ticker_service = TickerService()
    all_tickers = ticker_service.get_all_tickers()

    if not all_tickers:
        logger.error("No tickers found. Aborting.")
        return

    # 3. Sharding Logic
    chunk_size = math.ceil(len(all_tickers) / args.total_chunks)
    start_idx = args.chunk * chunk_size
    end_idx = min(start_idx + chunk_size, len(all_tickers))
    tickers_to_process = all_tickers[start_idx:end_idx]

    if not tickers_to_process:
        logger.warning(f"No tickers allocated for chunk {args.chunk}. Finishing.")
        return

    logger.info(
        f"Processing {len(tickers_to_process)} companies (out of {len(all_tickers)}) "
        f"in chunk {args.chunk} using optimized parallel batch mode..."
    )

    start_time = time.time()

    # 4. Run Async Loop
    asyncio.run(crawl_tickers_async(tickers_to_process))

    duration = time.time() - start_time
    logger.info(f"Crawling chunk {args.chunk} completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
