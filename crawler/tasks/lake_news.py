from loguru import logger

from core.database import session_local
from core.repositories import CompanyRepository
from core.services.lake_service import LakeService
from crawler.spiders.news_spider import NewsSpider


async def crawl_news_task():
    """Collect RSS news and tag entries against known tickers."""
    task_logger = logger.bind(task="lake.news")
    task_logger.info("Starting news collection (LagoAI data lake)...")

    db = session_local()
    try:
        company_repo = CompanyRepository(db)
        lake_service = LakeService(db)
        spider = NewsSpider(company_repo, lake_service)
        persisted = await spider.crawl_all()
        task_logger.info(f"News collection completed ({persisted} items).")
    except Exception as e:
        task_logger.error(f"News collection failed: {e}")
        raise
    finally:
        await db.close()
