import sys
import time

from loguru import logger

from core.config import settings
from crawler.services.ticker_service import TickerService
from crawler.tasks import crawl_macro_data_task, crawl_ticker_task


def _assert_redis_broker() -> None:
    broker = settings.REDIS_URL
    if not broker.startswith(("redis://", "rediss://")):
        logger.error(
            "REDIS_URL must point to a Redis broker (redis:// or rediss://), "
            "but resolved to {!r}. In GitHub Actions, ensure the REDIS_URL "
            "repository secret is set to your Redis URL.",
            broker,
        )
        sys.exit(1)


def enqueue_all():
    logger.info("Starting to enqueue daily jobs...")
    _assert_redis_broker()

    ticker_service = TickerService()
    all_tickers = ticker_service.get_all_tickers()

    if not all_tickers:
        logger.error("No tickers found to enqueue.")
        return

    logger.info("Enqueuing macro data task...")
    crawl_macro_data_task.delay()  # type: ignore[attr-defined] - Motivo: Celery dinâmico

    logger.info(f"Enqueuing crawl tasks for {len(all_tickers)} tickers...")

    count = 0
    for symbol in all_tickers:
        crawl_ticker_task.delay(symbol)  # type: ignore[attr-defined] - Motivo: Celery dinâmico
        count += 1
        if count % 50 == 0:
            logger.info(f"Enqueued {count}/{len(all_tickers)} tickers...")

    logger.info("Successfully enqueued all daily jobs.")


if __name__ == "__main__":
    start_time = time.time()
    enqueue_all()
    duration = time.time() - start_time
    logger.info(f"Enqueue process completed in {duration:.2f} seconds.")
