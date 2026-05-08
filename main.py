from crawler.services.database import SessionLocal, engine, Base
from crawler.tasks import crawl_ticker_task
from loguru import logger

def main():
    logger.info("Starting B3 Stock Market Crawler (Async Mode)...")
    
    # Example tickers
    tickers = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "B3SA3"]
    
    for ticker in tickers:
        logger.info(f"Queuing task for {ticker}")
        crawl_ticker_task.delay(ticker)
    
    logger.info(f"Queued {len(tickers)} tasks. Check Celery logs for progress.")

if __name__ == "__main__":
    main()
