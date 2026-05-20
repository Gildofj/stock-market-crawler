"""RI document collection task.

Runs in two contexts:
* As a Celery task (legacy local/dev path) — still routable via the `lake` queue.
* As a standalone Cloud Run Job entrypoint via ``python -m crawler.tasks.lake_ri``,
  which is how the production schedule invokes it (1x/day). The job uses the same
  container image as the workers but bypasses Celery entirely — no Redis hop, no
  beat coupling, dedicated RAM per execution so pdfplumber spikes can't OOM the VM.
"""

import asyncio

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from core.database import session_local
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from crawler.celery_app import app
from crawler.spiders.ri_spider import RISpider
from crawler.tasks._shared import _TRANSIENT_ERRORS, request_manager


def _run_ri_crawl(days_back: int = 30) -> int:
    """Pure crawl logic, callable from Celery or standalone."""
    db = session_local()
    try:
        company_repo = CompanyRepository(db)
        lake_service = LakeService(db)
        spider = RISpider(company_repo, lake_service, request_manager)
        return spider.crawl_recent(days_back=days_back)
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
    try:
        persisted = asyncio.run(_run_ri_crawl(days_back=days_back))
        task_logger.info(f"RI document collection completed ({persisted} docs).")
    except SoftTimeLimitExceeded:
        task_logger.warning("Soft time limit hit during RI crawl; aborting.")
        raise


def main() -> None:
    """Cloud Run Job entrypoint. Reads days_back from $RI_DAYS_BACK (default 7)."""
    import os

    from core.logging import setup_logging

    setup_logging()

    days_back = int(os.environ.get("RI_DAYS_BACK", "7"))
    job_logger = logger.bind(task="lake.ri", runtime="cloud_run_job")
    job_logger.info(f"Starting RI crawl (Cloud Run Job, days_back={days_back})...")
    asyncio.run(_run_ri_crawl(days_back=days_back))
    job_logger.info("RI crawl completed.")


if __name__ == "__main__":
    main()
