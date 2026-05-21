import sys
import time

from loguru import logger

from core.config import settings
from crawler.tasks import crawl_news_task, crawl_ri_task


def _assert_redis_broker() -> None:
    broker = settings.REDIS_URL
    if not broker.startswith(("redis://", "rediss://")):
        logger.error(
            "REDIS_URL must point to a Redis broker (redis:// or rediss://), but resolved to {!r}.",
            broker,
        )
        sys.exit(1)


def enqueue_all() -> None:
    logger.info("Enqueuing LagoAI lake jobs (news + RI)...")
    _assert_redis_broker()

    crawl_news_task.delay()  # type: ignore[attr-defined]
    crawl_ri_task.delay()  # type: ignore[attr-defined]

    logger.info("LagoAI lake jobs enqueued.")


if __name__ == "__main__":
    start_time = time.time()
    enqueue_all()
    duration = time.time() - start_time
    logger.info(f"Enqueue process completed in {duration:.2f} seconds.")
