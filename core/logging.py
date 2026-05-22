from __future__ import annotations

import logging
import sys
import traceback as tb_module
from datetime import UTC
from typing import Any

import orjson
from loguru import logger

from core.config import settings
from core.context import request_id_var, task_id_var, task_name_var

_GCP_SEVERITY: dict[str, str] = {
    "TRACE": "DEBUG",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "SUCCESS": "NOTICE",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}

_HUMAN_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
    "<level>{level: <8}</level> "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> "
    "- <level>{message}</level>"
)

_ERROR_REPORTING_TYPE = (
    "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent"
)

_CONFIGURED = False


def _trace_context() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None, None

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def _otel_patcher(record: Any) -> None:
    trace_id, span_id = _trace_context()
    if trace_id:
        record["extra"]["trace_id"] = trace_id
        record["extra"]["span_id"] = span_id

    rid = request_id_var.get()
    if rid:
        record["extra"]["request_id"] = rid

    tid = task_id_var.get()
    if tid:
        record["extra"]["task_id"] = tid
        tname = task_name_var.get()
        if tname:
            record["extra"]["task_name"] = tname


def _gcp_sink(message: Any) -> None:
    record = message.record
    extra = dict(record["extra"])
    trace_id = extra.pop("trace_id", None)
    span_id = extra.pop("span_id", None)

    payload: dict[str, Any] = {
        "severity": _GCP_SEVERITY.get(record["level"].name, "DEFAULT"),
        "message": record["message"],
        "timestamp": record["time"].astimezone(UTC).isoformat(),
        "logger": record["name"],
        "logging.googleapis.com/sourceLocation": {
            "file": record["file"].path,
            "line": str(record["line"]),
            "function": record["function"],
        },
        "serviceContext": {
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
        },
    }

    if trace_id:
        project = settings.GCP_PROJECT_ID
        payload["logging.googleapis.com/trace"] = (
            f"projects/{project}/traces/{trace_id}" if project else trace_id
        )
        payload["logging.googleapis.com/spanId"] = span_id

    if extra:
        payload["extra"] = extra

    exc = record["exception"]
    if exc is not None:
        payload["exception"] = "".join(
            tb_module.format_exception(exc.type, exc.value, exc.traceback)
        )
        payload["@type"] = _ERROR_REPORTING_TYPE

    sys.stdout.write(orjson.dumps(payload).decode() + "\n")
    sys.stdout.flush()


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()
    logger.configure(patcher=_otel_patcher)

    if settings.LOG_FORMAT == "gcp":
        logger.add(_gcp_sink, level=settings.LOG_LEVEL)
    else:
        logger.add(
            sys.stderr,
            level=settings.LOG_LEVEL,
            format=_HUMAN_FORMAT,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )

    intercept = _InterceptHandler()
    logging.basicConfig(handlers=[intercept], level=settings.LOG_LEVEL, force=True)
    for name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "celery",
        "celery.beat",
        "celery.worker",
        "sqlalchemy.engine",
        "kombu",
    ):
        std_logger = logging.getLogger(name)
        std_logger.handlers = [intercept]
        std_logger.propagate = False

    _CONFIGURED = True
