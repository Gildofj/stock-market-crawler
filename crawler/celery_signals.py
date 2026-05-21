"""Celery signal handlers bridging per-task state into :mod:`core.context`
and re-initializing OpenTelemetry inside prefork children.
"""

from __future__ import annotations

from typing import Any

from celery.signals import task_postrun, task_prerun, worker_process_init

from core.context import task_id_var, task_name_var
from core.telemetry import setup_tracing


@task_prerun.connect
def _on_task_prerun(task_id: str | None = None, task: Any = None, **_: Any) -> None:
    if task_id:
        task_id_var.set(task_id)
    if task is not None:
        task_name_var.set(getattr(task, "name", None))


@task_postrun.connect
def _on_task_postrun(**_: Any) -> None:
    task_id_var.set(None)
    task_name_var.set(None)


@worker_process_init.connect
def _on_worker_process_init(**_: Any) -> None:
    # BatchSpanProcessor's daemon thread does not survive fork; each prefork
    # child must rebuild its TracerProvider/exporter pipeline.
    import core.telemetry as telemetry

    telemetry._CONFIGURED_FOR = None
    setup_tracing("celery-worker")
