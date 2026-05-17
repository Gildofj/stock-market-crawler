from loguru import logger

from crawler.celery_app import app
from crawler.services.data_service import DataService
from crawler.services.database import session_local
from crawler.services.lake_service import LakeService
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

    db = session_local()
    try:
        data_service = DataService(db)
        lake_service = LakeService(db)
        spider = NewsSpider(data_service, lake_service)
        persisted = spider.crawl_all()
        task_logger.info(f"News collection completed ({persisted} items).")
    finally:
        db.close()
