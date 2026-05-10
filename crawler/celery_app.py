import sys

from celery import Celery
from loguru import logger

from crawler.services.config import settings

# Configure Loguru for JSON serialization to feed Grafana Loki perfectly
logger.remove()
logger.add(sys.stdout, serialize=True)

CELERY_BROKER_URL = settings.CELERY_BROKER_URL

# Mask password for security
masked_broker = CELERY_BROKER_URL.split('@')[-1] if '@' in CELERY_BROKER_URL else CELERY_BROKER_URL
logger.info(f"Connecting to Celery Broker at: ...@{masked_broker}")

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
    task_default_queue='stock_crawler',  # Isolamento: evita conflito com outros projetos
    # Rate limit: max 2 tasks per second across all workers
    # This prevents the 993 tickers from hitting APIs too fast
    task_annotations={
        'crawler.tasks.crawl_ticker_task': {'rate_limit': '2/s'}
    }
)

if __name__ == "__main__":
    app.start()
