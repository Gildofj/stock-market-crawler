from loguru import logger
from crawler.celery_app import app
from crawler.services.data_service import DataService
from crawler.services.database import SessionLocal
from crawler.services.etl_service import ETLService
from crawler.services.request_manager import RequestManager
from crawler.spiders.b3_spider import B3Spider
from crawler.spiders.fundamentus_spider import FundamentusSpider

request_manager = RequestManager()  # Can add proxy list here


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
        raise self.retry(exc=e) from None
    finally:
        db.close()
