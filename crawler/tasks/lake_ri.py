from loguru import logger

from core.database import session_local
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from crawler.spiders.ri_spider import RISpider
from crawler.tasks._shared import request_manager


async def _run_ri_crawl(days_back: int = 30) -> int:
    db = session_local()
    try:
        company_repo = CompanyRepository(db)
        lake_service = LakeService(db)
        spider = RISpider(company_repo, lake_service, request_manager)
        return await spider.crawl_recent(days_back=days_back)
    finally:
        await db.close()

async def crawl_ri_task(days_back: int = 30):
    task_logger = logger.bind(task="lake.ri")
    task_logger.info(f"Starting RI document collection (days_back={days_back})...")
    try:
        persisted = await _run_ri_crawl(days_back=days_back)
        task_logger.info(f"RI document collection completed ({persisted} docs).")
    except Exception as e:
        task_logger.error(f"RI document collection failed: {e}")
        raise

def main() -> None:
    import asyncio
    import os

    from core.logging import setup_logging
    from core.telemetry import setup_tracing, shutdown_tracing

    setup_logging()
    setup_tracing("ri-job")

    days_back = int(os.environ.get("RI_DAYS_BACK", "7"))
    job_logger = logger.bind(task="lake.ri", runtime="cloud_run_job")
    job_logger.info(f"Starting RI crawl (Cloud Run Job, days_back={days_back})...")
    try:
        asyncio.run(_run_ri_crawl(days_back=days_back))
        job_logger.info("RI crawl completed.")
    finally:
        shutdown_tracing()


if __name__ == "__main__":
    main()
