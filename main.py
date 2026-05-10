import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from crawler.engine.crawler_engine import CrawlerEngine
from crawler.services.database import session_local
from crawler.services.ticker_service import TickerService
from crawler.tasks import crawl_macro_data_task

# Concurrency control for external APIs
# max_api_concurrency=5 is the sweet spot for yfinance/Brapi without triggers 429
api_semaphore = threading.BoundedSemaphore(value=5)


def safe_crawl_ticker(symbol: str):
    """
    Executes a crawl task within the safety of the API semaphore.
    A new database session is created for each thread.
    """
    with api_semaphore:
        db = session_local()
        try:
            engine = CrawlerEngine(db)
            engine.run_for_ticker(symbol)
        except Exception as e:
            logger.error(f"Engine failed for {symbol}: {e}")
        finally:
            db.close()


def main():
    logger.info("Starting stock-market-crawler (Resilient Mode)...")

    # 1. Fetch Macro Data
    try:
        crawl_macro_data_task()
    except Exception as e:
        logger.error(f"Failed to fetch macro data: {e}")

    # 2. Fetch Tickers
    ticker_service = TickerService()
    tickers = ticker_service.get_all_tickers()

    if not tickers:
        logger.error("No tickers found. Aborting.")
        return

    # Process tickers with high thread count but controlled API access.
    # Total threads=15 for fast context switching, but only 5 hit the network at once.
    max_workers = 15
    logger.info(
        f"Processing {len(tickers)} companies using {max_workers} threads "
        "(Concurrent API Limit: 5)..."
    )

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit tasks to the executor
        futures = [executor.submit(safe_crawl_ticker, ticker) for ticker in tickers]

        # Wait for all to complete
        for future in futures:
            future.result()

    duration = time.time() - start_time
    logger.info(f"Crawling completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
