from celery.exceptions import SoftTimeLimitExceeded
from kombu.exceptions import OperationalError as KombuOperationalError
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from crawler.celery_app import app
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.services.data_service import DataService
from crawler.services.database import session_local
from crawler.services.etl_service import ETLService
from crawler.services.lake_service import LakeService
from crawler.services.reliability_service import ReliabilityService
from crawler.services.request_manager import RequestManager
from crawler.spiders.macro_spider import MacroSpider
from crawler.spiders.news_spider import NewsSpider
from crawler.spiders.ri_spider import RISpider

request_manager = RequestManager()

# Errors worth retrying — broker hiccups, DB blips, transient Redis I/O.
# Spider-level fetch errors are caught inside the spider and should NOT
# bubble up here, so this list stays narrow on purpose.
_TRANSIENT_ERRORS = (
    OperationalError,
    SQLAlchemyError,
    RedisError,
    KombuOperationalError,
    ConnectionError,
    TimeoutError,
)


@app.task(
    name="crawler.tasks.crawl_ticker_task",
    bind=True,
    autoretry_for=_TRANSIENT_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def crawl_ticker_task(self, symbol: str):
    """Crawl a single ticker via CrawlerEngine then run ETL + reliability."""
    task_logger = logger.bind(ticker=symbol, task_id=self.request.id)
    task_logger.info(f"Starting optimized crawl for {symbol}")

    db = session_local()
    try:
        engine = CrawlerEngine(db, request_manager)
        etl_service = ETLService(db)
        reliability_service = ReliabilityService(db)

        engine.run_for_ticker(symbol)

        company = engine.data_service.get_company_by_symbol(symbol)
        if company:
            etl_service.generate_features(company.id)
            reliability_service.compute_and_save(company.id)
            task_logger.info(f"Ticker {symbol} completed successfully.")
    except SoftTimeLimitExceeded:
        task_logger.warning(f"Soft time limit hit for {symbol}; aborting.")
        raise
    finally:
        db.close()


@app.task(
    name="crawler.tasks.crawl_macro_data_task",
    bind=True,
    autoretry_for=_TRANSIENT_ERRORS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def crawl_macro_data_task(self):
    """Fetch macroeconomic indicators (SELIC / IPCA) from BCB."""
    task_logger = logger.bind(task="macro", task_id=self.request.id)
    task_logger.info("Starting macro data collection...")

    db = session_local()
    try:
        data_service = DataService(db)
        macro_spider = MacroSpider(data_service, request_manager)
        macro_spider.crawl_macro_indicators()
        task_logger.info("Macro data collection completed.")
    finally:
        db.close()


@app.task(
    name="crawler.tasks.crawl_news_task",
    bind=True,
    autoretry_for=_TRANSIENT_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def crawl_news_task(self):
    """Collect RSS news and tag entries against known tickers."""
    task_logger = logger.bind(task="lake.news", task_id=self.request.id)
    task_logger.info("Starting news collection (LagoAI data lake)...")

    db = session_local()
    try:
        data_service = DataService(db)
        lake_service = LakeService(db)
        spider = NewsSpider(data_service, lake_service)
        persisted = spider.crawl_all()
        task_logger.info(f"News collection completed ({persisted} items).")
    finally:
        db.close()


@app.task(
    name="crawler.tasks.crawl_ri_task",
    bind=True,
    autoretry_for=_TRANSIENT_ERRORS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=1500,
    time_limit=1800,
)
def crawl_ri_task(self, days_back: int = 30):
    """Collect CVM RI documents (ITR / DFP / IPE) for watched companies."""
    task_logger = logger.bind(task="lake.ri", task_id=self.request.id)
    task_logger.info(f"Starting RI document collection (days_back={days_back})...")

    db = session_local()
    try:
        data_service = DataService(db)
        lake_service = LakeService(db)
        spider = RISpider(data_service, lake_service, request_manager)
        persisted = spider.crawl_recent(days_back=days_back)
        task_logger.info(f"RI document collection completed ({persisted} docs).")
    except SoftTimeLimitExceeded:
        task_logger.warning("Soft time limit hit during RI crawl; aborting.")
        raise
    finally:
        db.close()
