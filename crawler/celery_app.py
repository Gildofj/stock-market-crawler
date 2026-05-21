"""Celery app for a single-VM, self-hosted Redis deployment on GCE e2-micro.

Workers are recycled on a per-child memory ceiling so a rogue ``pdfplumber``
parse cannot OOM the 1 GB VM. Beat runs embedded inside the worker process
(no Cloud Scheduler) and every scheduled task must be idempotent — the
schedule file is ephemeral and may double-fire on restart.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from core.config import settings
from core.logging import setup_logging
from core.telemetry import setup_tracing

setup_logging()
setup_tracing("celery-worker")

# Side-effect import: registers task_prerun/postrun + worker_process_init signals.
from crawler import celery_signals  # noqa: E402, F401

app = Celery(
    "stock_market_crawler",
    broker=settings.redis_url,
    include=[
        "crawler.tasks.ticker",
        "crawler.tasks.lake_news",
        "crawler.tasks.lake_ri",
        "crawler.tasks.macro",
    ],
)

app.conf.update(
    # No code path calls AsyncResult.get(); disabling the backend cuts Redis
    # command volume by ~half.
    result_backend=None,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_track_started=False,
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    # 200 MB ceiling fits worker-hot (concurrency=2) + worker-lake
    # (concurrency=1) under ~900 MB on the 1 GB e2-micro.
    worker_max_memory_per_child=200_000,
    worker_send_task_events=False,
    worker_enable_remote_control=False,
    worker_disable_rate_limits=True,
    worker_hijack_root_logger=False,
    # Default redirect captures sys.stdout into the `celery.redirected` logger
    # at WARNING level, silently dropping INFO-level JSON written by
    # core.logging._gcp_sink and creating a feedback loop on WARNING+.
    worker_redirect_stdouts=False,
    broker_pool_limit=10,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_heartbeat=None,
    broker_transport_options={
        # Must exceed the longest task; RI PDF parses can take minutes.
        "visibility_timeout": 3600,
        "socket_keepalive": True,
        "polling_interval": 0.5,
        "max_retries": 5,
        "interval_start": 1.0,
        "interval_step": 2.0,
        "interval_max": 30.0,
    },
    task_default_queue="default",
    task_queues=(
        Queue("default"),
        Queue("crawler"),
        Queue("lake"),
        Queue("macro"),
    ),
    task_routes={
        "crawler.tasks.crawl_ticker_task": {"queue": "crawler"},
        "crawler.tasks.crawl_news_task": {"queue": "lake"},
        # crawl_ri_task runs as a Cloud Run Job, not via Celery — intentionally unrouted.
        "crawler.tasks.crawl_macro_data_task": {"queue": "macro"},
    },
    # Hours are UTC (Brazil = UTC-3). RI crawl is on Cloud Scheduler, not here.
    beat_schedule={
        "lake-news-hourly": {
            "task": "crawler.tasks.crawl_news_task",
            "schedule": crontab(minute=0),
        },
        "macro-daily": {
            "task": "crawler.tasks.crawl_macro_data_task",
            "schedule": crontab(minute=0, hour=11),
        },
    },
    beat_max_loop_interval=300,
)


if __name__ == "__main__":
    app.start()
