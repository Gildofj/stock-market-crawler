from loguru import logger

from crawler.celery_app import app
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.services.data_service import DataService
from crawler.services.database import session_local
from crawler.services.etl_service import ETLService
from crawler.services.reliability_service import ReliabilityService
from crawler.services.request_manager import RequestManager
from crawler.spiders.macro_spider import MacroSpider

request_manager = RequestManager()  # Can add proxy list here


@app.task(name="crawler.tasks.crawl_ticker_task", bind=True, max_retries=3)
def crawl_ticker_task(self, symbol: str):
    """Sync function to crawl a single ticker from multiple sources via CrawlerEngine."""
    # Bind the symbol to the logger for tracing
    task_logger = logger.bind(ticker=symbol)

    task_logger.info(f"Starting optimized crawl for {symbol}")
    db = session_local()
    try:
        engine = CrawlerEngine(db, request_manager)
        etl_service = ETLService(db)
        reliability_service = ReliabilityService(db)

        # 1. Multi-source Orchestrated Crawl
        engine.run_for_ticker(symbol)

        # 2. ETL Pipeline (Generate ML Features)
        company = engine.data_service.get_company_by_symbol(symbol)
        if company:
            etl_service.generate_features(company.id)

            # 3. Reliability Scoring (runs after fresh Fundamental row is persisted)
            reliability_service.compute_and_save(company.id)

            task_logger.info(f"Ticker {symbol} completed successfully.")

    except Exception as e:
        task_logger.error(f"Task for {symbol} failed: {e}")
        # Retry logic could be added here if needed:
        # raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@app.task(name="crawler.tasks.crawl_macro_data_task")
def crawl_macro_data_task():
    """Sync task to fetch macro indicators."""
    logger.info("Starting macro data collection...")
    db = session_local()
    try:
        data_service = DataService(db)
        macro_spider = MacroSpider(data_service, request_manager)
        macro_spider.crawl_macro_indicators()
        logger.info("Macro data collection completed.")
    except Exception as e:
        logger.error(f"Macro task failed: {e}")
    finally:
        db.close()
