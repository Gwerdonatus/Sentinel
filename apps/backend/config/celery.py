"""
Sentinel Celery Application.

All async task processing runs through this Celery app.
Phase 1: Redis as broker.
Phase 2+: Kafka replaces Redis for event streaming tasks.
"""

from __future__ import annotations

import os

from celery import Celery
from celery.signals import worker_process_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("sentinel")

# Load configuration from Django settings, using CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@worker_process_init.connect(weak=False)
def init_worker_otel(**kwargs: object) -> None:
    """Initialize OpenTelemetry in Celery worker processes.

    Each worker process is a separate process — OTEL must be
    initialized per-process, not just in the main Django process.
    """
    from django.conf import settings

    if not settings.OTEL_ENABLED:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            SERVICE_NAME: f"{settings.OTEL_SERVICE_NAME}-worker",
            SERVICE_VERSION: settings.OTEL_SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()


@app.task(bind=True, ignore_result=True)
def debug_task(self: Celery) -> None:
    """Debug task for verifying Celery connectivity."""
    print(f"Request: {self.request!r}")  # noqa: T201
