from loguru import logger
from crawler.tasks import crawl_ticker_task
from crawler.services.ticker_service import TickerService

def main():
    logger.info("Starting stock-market-crawler (Full Market Discovery)...")
    
    ticker_service = TickerService()
    tickers = ticker_service.get_all_tickers()
    
    if not tickers:
        logger.error("No tickers found. Aborting.")
        return

    logger.info(f"Distributing tasks for {len(tickers)} companies across the cluster...")
    
    for ticker in tickers:
        # We process in background via Celery
        crawl_ticker_task.delay(ticker)

    logger.info("All tasks dispatched. Workers are processing the data.")


if __name__ == "__main__":
    main()
