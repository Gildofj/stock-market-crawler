import time

from loguru import logger

from core.services.cloud_tasks_service import CloudTasksService


def enqueue_all() -> None:
    logger.info("Enqueuing LagoAI lake jobs (news + RI)...")

    tasks_service = CloudTasksService()

    tasks_service.enqueue_task("/_tasks/news")
    tasks_service.enqueue_task("/_tasks/ri")

    logger.info("LagoAI lake jobs enqueued.")


if __name__ == "__main__":
    start_time = time.time()
    enqueue_all()
    duration = time.time() - start_time
    logger.info(f"Enqueue process completed in {duration:.2f} seconds.")
