import time
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from crawler.services.ticker_service import TickerService
from crawler.tasks import crawl_macro_data_task, crawl_ticker_task


def main():
    logger.info("Starting stock-market-crawler (GitHub Actions Mode)...")

    # 1. Fetch Macro Data (Once per run)
    try:
        crawl_macro_data_task()
    except Exception as e:
        logger.error(f"Failed to fetch macro data: {e}")

    # 2. Fetch all Tickers
    ticker_service = TickerService()
    tickers = ticker_service.get_all_tickers()

    if not tickers:
        logger.error("No tickers found. Aborting.")
        return

    # Use ThreadPoolExecutor to process tickers in parallel.
    # max_workers=5 is a safe limit for Supabase Free Tier (which has a connection limit).
    # This also prevents the GitHub Action from being throttled by external APIs.
    MAX_WORKERS = 5
    logger.info(f"Processing {len(tickers)} companies using {MAX_WORKERS} parallel workers...")

    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # map handles the distribution of tickers to the pool
        executor.map(crawl_ticker_task, tickers)

    duration = time.time() - start_time
    logger.info(f"Crawling completed in {duration:.2f} seconds.")


if __name__ == "__main__":
    main()
