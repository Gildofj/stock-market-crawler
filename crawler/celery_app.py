import os
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# We name it 'stock_crawler' to avoid confusion with the 'crawler' package
app = Celery(
    "stock_crawler",
    broker=CELERY_BROKER_URL,
    include=["crawler.tasks"]
)

# Optional configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

if __name__ == "__main__":
    app.start()
