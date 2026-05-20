"""OpenTelemetry tracing setup for the stock market crawler.

``setup_tracing(service_name)`` is idempotent per ``service_name`` and safe to
call from re-entrant contexts:

* From ``api/main.py`` once at module import (before ``FastAPI()``).
* From ``crawler/celery_app.py`` once at module import.
* Again from the Celery ``worker_process_init`` signal, because the
  ``BatchSpanProcessor`` daemon thread does not survive ``fork`` in prefork
  pools — each child re-runs setup so its thread is alive.

Every instrumentation step is wrapped in a best-effort guard: a missing
instrumentor package degrades to "no spans for that integration" rather than
preventing the app from booting.

Configuration is read from :class:`core.config.Settings`:

* ``OTEL_ENABLED`` — global kill switch (default ``False``)
* ``OTEL_EXPORTER`` — ``console`` | ``otlp`` | ``gcp``
* ``OTEL_SAMPLE_RATIO`` — wrapped in ``ParentBased(TraceIdRatioBased)``
* ``OTEL_INSTRUMENT_REDIS`` — opt-in for the Redis instrumentor

Standard OTel SDK env vars (``OTEL_EXPORTER_OTLP_ENDPOINT``,
``OTEL_PYTHON_FASTAPI_EXCLUDED_URLS``, ...) are consumed by the SDK directly.
"""

from __future__ import annotations

import importlib
from typing import Any

from loguru import logger

from core.config import settings

_CONFIGURED_FOR: str | None = None


def setup_tracing(service_name: str) -> None:
    """Initialize the OTel SDK and best-effort auto-instrumentation."""
    global _CONFIGURED_FOR
    if not settings.OTEL_ENABLED:
        return
    if _CONFIGURED_FOR == service_name:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning(
            "OTEL_ENABLED=true but opentelemetry SDK not installed. "
            "Run `uv sync --extra observability`. Tracing disabled."
        )
        return

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": settings.SERVICE_NAME,
            "service.version": settings.SERVICE_VERSION,
            "deployment.environment": settings.DEPLOYMENT_ENV,
        }
    )
    sampler = ParentBased(root=TraceIdRatioBased(settings.OTEL_SAMPLE_RATIO))
    provider = TracerProvider(resource=resource, sampler=sampler)

    exporter = _build_exporter()
    if exporter is not None:
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                schedule_delay_millis=2000,
                max_queue_size=512,
                max_export_batch_size=128,
            )
        )

    trace.set_tracer_provider(provider)
    _install_instrumentations()

    _CONFIGURED_FOR = service_name
    logger.info(
        f"OpenTelemetry tracing enabled (service={service_name}, "
        f"exporter={settings.OTEL_EXPORTER}, sample_ratio={settings.OTEL_SAMPLE_RATIO})"
    )


def _build_exporter() -> Any:
    backend = settings.OTEL_EXPORTER
    try:
        if backend == "otlp":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter()
        if backend == "gcp":
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

            return CloudTraceSpanExporter(project_id=settings.GCP_PROJECT_ID)
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return ConsoleSpanExporter()
    except ImportError as exc:
        logger.warning(f"OTel exporter '{backend}' unavailable: {exc}. Tracing degraded.")
        return None


def _install_instrumentations() -> None:
    _instrument("fastapi", "opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor")
    _instrument(
        "sqlalchemy", "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor"
    )
    _instrument("celery", "opentelemetry.instrumentation.celery", "CeleryInstrumentor")
    _instrument("httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor")
    if settings.OTEL_INSTRUMENT_REDIS:
        _instrument("redis", "opentelemetry.instrumentation.redis", "RedisInstrumentor")


def _instrument(label: str, module: str, klass: str) -> None:
    try:
        mod = importlib.import_module(module)
        getattr(mod, klass)().instrument()
    except ImportError:
        logger.debug(f"OTel instrumentor for {label} not installed; skipping.")
    except Exception as exc:
        # Most instrumentors raise on a second .instrument() call — that's
        # fine and matches the idempotency contract of setup_tracing().
        if "already instrumented" in str(exc).lower():
            return
        logger.warning(f"Failed to install OTel instrumentor for {label}: {exc}")


def shutdown_tracing() -> None:
    """Flush pending spans. Call from the Cloud Run Job entrypoint before exit."""
    if _CONFIGURED_FOR is None:
        return
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception as exc:
        logger.warning(f"OTel shutdown failed: {exc}")
