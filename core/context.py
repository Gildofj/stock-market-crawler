"""ContextVars read by the loguru patcher in :mod:`core.logging` so a single
``request_id`` or ``task_id`` groups every log emitted during that
request/task across SQLAlchemy, httpx and the crawler engine.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)
task_name_var: ContextVar[str | None] = ContextVar("task_name", default=None)
