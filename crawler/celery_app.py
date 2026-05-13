from celery import Celery
from crawler.services.config import settings

app = Celery(
    "stock_market_crawler",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["crawler.tasks"]
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

if __name__ == "__main__":
    app.start()
