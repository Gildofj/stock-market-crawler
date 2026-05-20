"""Per-execution context shared across logging, middleware and Celery tasks.

These ContextVars are read by the loguru patcher in :mod:`core.logging` and
attached to every log line, so a single ``request_id`` (HTTP) or ``task_id``
(Celery) groups together every log emitted while serving that request or task
— across SQLAlchemy, httpx and the crawler engine — without each layer having
to thread an identifier through its call chain.

ContextVars propagate automatically across ``await`` and across new asyncio
tasks via ``contextvars.copy_context``; in Celery prefork pools, the per-task
isolation is enforced by the ``task_prerun``/``task_postrun`` signals in
:mod:`crawler.celery_signals`.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)
task_name_var: ContextVar[str | None] = ContextVar("task_name", default=None)
