from loguru import logger
from crawler.tasks import crawl_ticker_task, crawl_macro_data_task
from crawler.services.ticker_service import TickerService
from crawler.models.models import Base
from crawler.services.database import engine

def main():
    logger.info("Starting stock-market-crawler (Full Market Discovery)...")
    
    # 0. Initialize DB Schema (Migrations are preferred for production)
    logger.info("Initializing database schema...")
    # Base.metadata.create_all(bind=engine) # Alternative: uv run alembic upgrade head
    
    # 1. Fetch Macro Data (Once per run)
    logger.info("Triggering macro data collection...")
    crawl_macro_data_task.delay()
    
    # 2. Fetch all Tickers
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
