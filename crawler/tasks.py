from loguru import logger

from crawler.celery_app import app
from crawler.services.data_service import DataService
from crawler.services.database import SessionLocal
from crawler.services.etl_service import ETLService
from crawler.services.request_manager import RequestManager
from crawler.spiders.b3_spider import B3Spider
from crawler.spiders.fundamentus_spider import FundamentusSpider
from crawler.spiders.macro_spider import MacroSpider
from crawler.spiders.statusinvest_spider import StatusInvestSpider

request_manager = RequestManager()  # Can add proxy list here


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_ticker_task(self, symbol: str):
    # Bind the symbol to the logger for tracing in Loki
    task_logger = logger.bind(ticker=symbol, task_id=self.request.id)

    task_logger.info(f"Starting multi-source crawl for {symbol}")
    db = SessionLocal()
    try:
        data_service = DataService(db)
        etl_service = ETLService(db)

        # 1. Price Data & Initial Fundamentals (yfinance)
        yfinance_spider = B3Spider(data_service)
        yfinance_spider.crawl_ticker(symbol)

        # 2. Advanced Fundamentals (Scraping Fundamentus)
        fundamentus_spider = FundamentusSpider(data_service)
        fundamentus_spider.crawl_ticker(symbol)

        # 3. Quality Check & Refinement (Scraping StatusInvest)
        # This provides a second opinion on P/L and P/VP
        status_spider = StatusInvestSpider(data_service)
        status_spider.crawl_ticker(symbol)

        # 4. ETL Pipeline (Generate ML Features)
        company = data_service.get_company_by_symbol(symbol)
        if company:
            etl_service.generate_features(company.id)
            task_logger.info("ETL pipeline completed successfully with multi-source data.")

    except Exception as e:
        task_logger.error(f"Task failed: {e}")
        raise self.retry(exc=e) from None
    finally:
        db.close()

@app.task
def crawl_macro_data_task():
    """Daily task to fetch macro indicators."""
    db = SessionLocal()
    try:
        data_service = DataService(db)
        macro_spider = MacroSpider(data_service)
        macro_spider.crawl_macro_indicators()
    finally:
        db.close()
