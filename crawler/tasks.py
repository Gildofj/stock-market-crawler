import os
from celery import Celery
from .services.database import SessionLocal
from .services.data_service import DataService
from .services.etl_service import ETLService
from .services.request_manager import RequestManager
from .spiders.b3_spider import B3Spider
from .spiders.fundamentus_spider import FundamentusSpider
from loguru import logger

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

app = Celery("crawler", broker=CELERY_BROKER_URL)
request_manager = RequestManager() # Can add proxy list here

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_ticker_task(self, symbol: str):
    logger.info(f"Starting async crawl for {symbol}")
    db = SessionLocal()
    try:
        data_service = DataService(db)
        etl_service = ETLService(db)
        
        # 1. Price Data (yfinance)
        yfinance_spider = B3Spider(data_service)
        yfinance_spider.crawl_ticker(symbol)
        
        # 2. Fundamental Data (Scraping Fundamentus)
        # We can pass request_manager to spiders if they support it
        fundamentus_spider = FundamentusSpider(data_service)
        fundamentus_spider.crawl_ticker(symbol)
        
        # 3. ETL Pipeline (Generate ML Features)
        company = data_service.get_company_by_symbol(symbol)
        if company:
            etl_service.generate_features(company.id)
        
    except Exception as e:
        logger.error(f"Task failed for {symbol}: {e}")
        raise self.retry(exc=e)
    finally:
        db.close()
