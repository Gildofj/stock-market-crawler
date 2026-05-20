import asyncio
from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from core.database import session_local
from core.services.etl_service import ETLService
from core.services.reliability_service import ReliabilityService
from crawler.celery_app import app
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.tasks._shared import _TRANSIENT_ERRORS, request_manager


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

    async def _run():
        db = session_local()
        try:
            engine = CrawlerEngine(db, request_manager)
            etl_service = ETLService(db)
            reliability_service = ReliabilityService(db)

            await engine.run_for_ticker(symbol)

            company = await engine.company_repo.get_by_symbol(symbol)
            if company:
                await etl_service.generate_features(company.id)
                await reliability_service.compute_and_save(company.id)
                task_logger.info(f"Ticker {symbol} completed successfully.")
        except SoftTimeLimitExceeded:
            task_logger.warning(f"Soft time limit hit for {symbol}; aborting.")
            raise
        finally:
            await db.close()

    asyncio.run(_run())
