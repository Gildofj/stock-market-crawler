from loguru import logger

from core.database import session_local
from crawler.spiders.macro_spider import MacroSpider
from crawler.tasks._shared import request_manager


async def crawl_macro_data_task():
    """Fetch macroeconomic indicators (SELIC / IPCA) from BCB."""
    task_logger = logger.bind(task="macro")
    task_logger.info("Starting macro data collection...")

    db = session_local()
    try:
        macro_spider = MacroSpider(request_manager)
        await macro_spider.crawl_macro_indicators()
        task_logger.info("Macro data collection completed.")
    except Exception as e:
        task_logger.error(f"Macro data collection failed: {e}")
        raise
    finally:
        await db.close()
