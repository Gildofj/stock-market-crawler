"""Celery application configured for a single-VM, Upstash-Redis, free-tier deployment.

Design constraints
------------------
* **Upstash free tier**: command budget is the binding limit. We disable the
  result backend and stretch BLPOP polling to keep idle traffic minimal.
* **GCP e2-micro (1 GB RAM)**: workers are recycled on a memory ceiling so a
  rogue ``pdfplumber`` parse cannot OOM the VM.
* **No external scheduler**: beat runs embedded inside the worker process so we
  do not pay for Cloud Scheduler / Cloud Run Jobs. All scheduled tasks are
  idempotent (DB upserts) which makes the ephemeral schedule file harmless.
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from crawler.services.config import settings

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
    # ── Result backend ───────────────────────────────────────────────
    # Disabled on purpose: task outputs are persisted to Postgres inside
    # the task body, and nothing in the codebase calls AsyncResult.get().
    # Disabling cuts Redis command volume by roughly half.
    result_backend=None,
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,

    # ── Serialization / clock ────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # ── Reliability ──────────────────────────────────────────────────
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_track_started=False,  # avoids writes to the (absent) backend

    # ── Worker pool ──────────────────────────────────────────────────
    # concurrency=2 fits the e2-micro IO-bound workload. Memory ceiling
    # is set per child so pdfplumber/pandas spikes recycle that worker
    # instead of taking down the whole VM.
    worker_concurrency=2,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    # 200 MB ceiling fits two Celery processes on a 1 GB e2-micro: worker-hot
    # (concurrency=2) + worker-lake (concurrency=1) stay under ~900 MB worst-case
    # even when every child is at its peak. See terraform/compute_engine.tf.
    worker_max_memory_per_child=200_000,  # 200 MB (units: KiB)
    worker_send_task_events=False,
    worker_enable_remote_control=False,
    worker_disable_rate_limits=True,
    worker_hijack_root_logger=False,

    # ── Broker (Upstash Redis) ───────────────────────────────────────
    broker_pool_limit=5,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_heartbeat=None,
    broker_transport_options={
        # Visibility timeout must exceed the longest task. RI PDF parses
        # can take a couple of minutes per document, so 1h is generous.
        "visibility_timeout": 3600,
        "socket_keepalive": True,
        # 5s BLPOP idle interval keeps Upstash usage under ~17k cmds/day
        # in a fully idle worker — comfortably inside the free quota.
        "polling_interval": 5.0,
        "max_retries": 5,
        "interval_start": 1.0,
        "interval_step": 2.0,
        "interval_max": 30.0,
    },

    # ── Queues / routing ─────────────────────────────────────────────
    # One worker consumes all queues today, but naming them now lets us
    # split into dedicated workers later with zero code changes.
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
        # crawl_ri_task is intentionally NOT routed: it runs as a Cloud Run Job
        # (entrypoint: ``python -m crawler.tasks.lake_ri``), not via Celery.
        # The task decorator is kept so local dev / tests can still invoke it.
        "crawler.tasks.crawl_macro_data_task": {"queue": "macro"},
    },

    # ── Embedded beat schedule ───────────────────────────────────────
    # Hours are UTC. Brazil = UTC-3.
    # RI crawl is scheduled by Cloud Scheduler → Cloud Run Job, not here.
    beat_schedule={
        "lake-news-hourly": {
            "task": "crawler.tasks.crawl_news_task",
            "schedule": crontab(minute=0),
        },
        "macro-daily": {
            "task": "crawler.tasks.crawl_macro_data_task",
            "schedule": crontab(minute=0, hour=11),  # 08:00 BRT
        },
    },
    beat_max_loop_interval=300,
)


if __name__ == "__main__":
    app.start()
