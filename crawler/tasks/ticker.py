from loguru import logger

from core.database import session_local
from core.repositories.company_repository import CompanyRepository
from core.services.etl_service import ETLService
from core.services.reliability_service import ReliabilityService
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.tasks._shared import request_manager


async def crawl_ticker_task(symbol: str):
    """Crawl a single ticker via CrawlerEngine then run ETL + reliability.

    Uses two AsyncSessions instead of one big one: the engine stage may
    invoke ReconciliationService, which rolls back on failure but still
    breaks transaction isolation guarantees mid-task. Splitting into
    crawl-session and post-session keeps pool churn minimal (2 acquires)
    while preserving the failure-isolation [[feedback_session_isolation]].
    """
    task_logger = logger.bind(ticker=symbol)
    task_logger.info(f"Starting optimized crawl for {symbol}")

    try:
        async with session_local() as crawl_db:
            engine = CrawlerEngine(crawl_db, request_manager)
            await engine.run_for_ticker(symbol)

        async with session_local() as post_db:
            company = await CompanyRepository(post_db).get_by_symbol(symbol)
            if company is None:
                task_logger.warning(f"Ticker {symbol} not found after crawl; skipping ETL.")
                return
            company_id = company.id

            await ETLService(post_db).generate_features(company_id)
            await ReliabilityService(post_db).compute_and_save(company_id)

        task_logger.info(f"Ticker {symbol} completed successfully.")
    except Exception as e:
        task_logger.error(f"Task failed for {symbol}: {e}")
        raise
