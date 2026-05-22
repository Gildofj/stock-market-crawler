from __future__ import annotations

import importlib
from typing import Any

from loguru import logger

from core.config import settings

_CONFIGURED_FOR: str | None = None


def setup_tracing(service_name: str) -> None:
    global _CONFIGURED_FOR
    if not settings.OTEL_ENABLED:
        return
    if _CONFIGURED_FOR == service_name:
        return

    try:
        from opentelemetry import trace  # type: ignore - Motivo: Tipagem externa
        from opentelemetry.sdk.resources import Resource  # type: ignore - Motivo: Tipagem externa
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore - Motivo: Tipagem externa
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore - Motivo: Externa
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased  # type: ignore - Motivo: Externa
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
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore - Motivo: Externa

            return OTLPSpanExporter()
        if backend == "gcp":
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter  # type: ignore - Motivo: Externa

            return CloudTraceSpanExporter(project_id=settings.GCP_PROJECT_ID)

        from opentelemetry.sdk.trace.export import ConsoleSpanExporter  # type: ignore - Motivo: Externa

        return ConsoleSpanExporter()
    except ImportError as exc:
        logger.warning(f"OTel exporter '{backend}' unavailable: {exc}. Tracing degraded.")
        return None


def _install_instrumentations() -> None:
    _instrument("fastapi", "opentelemetry.instrumentation.fastapi", "FastAPIInstrumentor")
    _instrument("sqlalchemy", "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor")
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
        if "already instrumented" in str(exc).lower():
            return
        logger.warning(f"Failed to install OTel instrumentor for {label}: {exc}")


def shutdown_tracing() -> None:
    if _CONFIGURED_FOR is None:
        return
    try:
        from opentelemetry import trace  # type: ignore - Motivo: Tipagem externa

        provider = trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception as exc:
        logger.warning(f"OTel shutdown failed: {exc}")
