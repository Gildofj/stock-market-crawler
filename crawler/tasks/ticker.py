from loguru import logger

from core.database import session_local
from core.services.etl_service import ETLService
from core.services.reliability_service import ReliabilityService
from crawler.engine.crawler_engine import CrawlerEngine
from crawler.tasks._shared import request_manager


async def crawl_ticker_task(symbol: str):
    """Crawl a single ticker via CrawlerEngine then run ETL + reliability."""
    task_logger = logger.bind(ticker=symbol)
    task_logger.info(f"Starting optimized crawl for {symbol}")

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
    except Exception as e:
        task_logger.error(f"Task failed for {symbol}: {e}")
        raise
    finally:
        await db.close()
