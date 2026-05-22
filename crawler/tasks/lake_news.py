import asyncio

from loguru import logger

from core.database import session_local
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from crawler.celery_app import app
from crawler.spiders.news_spider import NewsSpider
from crawler.tasks._shared import _TRANSIENT_ERRORS


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

    async def _run():
        db = session_local()
        try:
            company_repo = CompanyRepository(db)
            lake_service = LakeService(db)
            spider = NewsSpider(company_repo, lake_service)
            persisted = await spider.crawl_all()
            task_logger.info(f"News collection completed ({persisted} items).")
        finally:
            await db.close()

    asyncio.run(_run())
