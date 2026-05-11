import argparse
import asyncio
import math
import time

from loguru import logger

from crawler.engine.crawler_engine import CrawlerEngine
from crawler.services.database import session_local
from crawler.services.request_manager import RequestManager
from crawler.services.ticker_service import TickerService
from crawler.spiders.b3_spider import B3Spider
from crawler.spiders.fundamentus_spider import FundamentusSpider
from crawler.spiders.statusinvest_spider import StatusInvestSpider
from crawler.tasks import crawl_macro_data_task

# Concurrency control for async operations
# Increased to 10 for better async performance while still being mindful of rate limits
api_semaphore = asyncio.Semaphore(10)


async def safe_crawl_ticker(symbol: str, request_manager: RequestManager, spiders: dict):
    """
    Executes a crawl task within the safety of the async semaphore.
    Uses a new database session per ticker for thread/async safety.
    """
    async with api_semaphore:
        db = session_local()
        try:
            # Create a new engine with a fresh DB session but shared spiders
            engine = CrawlerEngine(db, request_manager=request_manager, spiders=spiders)
            await engine.run_for_ticker_async(symbol)
        except Exception as e:
            logger.error(f"Engine failed for {symbol}: {e}")
        finally:
            db.close()


async def crawl_tickers_async(tickers: list[str]):
    """
    Orchestrates the asynchronous crawling of a list of tickers.
    """
    request_manager = RequestManager()
    
    # Pre-initialize spiders to share them (and their caches) across tasks
    spiders = {
        "b3": B3Spider(),
        "fundamentus": FundamentusSpider(request_manager),
        "status": StatusInvestSpider(request_manager),
    }
    
    try:
        tasks = [safe_crawl_ticker(ticker, request_manager, spiders) for ticker in tickers]
        await asyncio.gather(*tasks)
    finally:
        await request_manager.close()


def main():
    parser = argparse.ArgumentParser(description="Stock Market Crawler")
    parser.add_argument("--chunk", type=int, default=0, help="Chunk index (0-based)")
    parser.add_argument("--total-chunks", type=int, default=1, help="Total number of chunks")
    args = parser.parse_args()

    logger.info(f"Starting stock-market-crawler (Async Mode) - Chunk {args.chunk}/{args.total_chunks}...")

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
        f"in chunk {args.chunk} using asyncio..."
    )

    start_time = time.time()

    # 4. Run Async Loop
    asyncio.run(crawl_tickers_async(tickers_to_process))

    duration = time.time() - start_time
    logger.info(f"Crawling chunk {args.chunk} completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
