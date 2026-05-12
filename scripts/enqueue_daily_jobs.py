import time
from loguru import logger
from crawler.services.ticker_service import TickerService
from crawler.tasks import crawl_macro_data_task, crawl_ticker_task

def enqueue_all():
    logger.info("Starting to enqueue daily jobs...")
    
    # 1. Enqueue Macro Data Task
    logger.info("Enqueuing macro data task...")
    crawl_macro_data_task.delay()
    
    # 2. Fetch Tickers
    ticker_service = TickerService()
    all_tickers = ticker_service.get_all_tickers()
    
    if not all_tickers:
        logger.error("No tickers found to enqueue.")
        return
        
    logger.info(f"Enqueuing crawl tasks for {len(all_tickers)} tickers...")
    
    count = 0
    for symbol in all_tickers:
        crawl_ticker_task.delay(symbol)
        count += 1
        if count % 50 == 0:
            logger.info(f"Enqueued {count}/{len(all_tickers)} tickers...")
            
    logger.info("Successfully enqueued all daily jobs.")

if __name__ == "__main__":
    start_time = time.time()
    enqueue_all()
    duration = time.time() - start_time
    logger.info(f"Enqueue process completed in {duration:.2f} seconds.")
