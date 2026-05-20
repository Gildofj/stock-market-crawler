"""Celery signal handlers bridging per-task state into :mod:`core.context`.

* ``task_prerun``  — populates ``task_id_var`` / ``task_name_var`` so every log
  emitted by the task body carries ``task_id`` and ``task_name``.
* ``task_postrun`` — clears them so a stray log between tasks does not
  mis-attribute itself to the previous one.

PR 3 will extend this module with a ``worker_process_init`` handler that
re-initializes the OpenTelemetry SDK inside each Celery prefork child (the
``BatchSpanProcessor`` daemon thread does not survive ``fork``).
"""

from __future__ import annotations

from typing import Any

from celery.signals import task_postrun, task_prerun

from core.context import task_id_var, task_name_var


@task_prerun.connect
def _on_task_prerun(
    task_id: str | None = None, task: Any = None, **_: Any
) -> None:
    if task_id:
        task_id_var.set(task_id)
    if task is not None:
        task_name_var.set(getattr(task, "name", None))


@task_postrun.connect
def _on_task_postrun(**_: Any) -> None:
    task_id_var.set(None)
    task_name_var.set(None)
