import asyncio

from loguru import logger

from core.database import session_local
from crawler.celery_app import app
from crawler.spiders.macro_spider import MacroSpider
from crawler.tasks._shared import _TRANSIENT_ERRORS, request_manager


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

    async def _run():
        db = session_local()
        try:
            # MacroSpider is currently sync but its constructor or methods might
            # interact with the database (which is now async).
            macro_spider = MacroSpider(request_manager)
            macro_spider.crawl_macro_indicators()
            task_logger.info("Macro data collection completed.")
        finally:
            await db.close()

    asyncio.run(_run())
