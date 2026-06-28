"""
Sentinel WSGI Application.

This is the entry point for production WSGI servers (Gunicorn).
OpenTelemetry auto-instrumentation is applied here, before Django initializes,
ensuring every request is traced from the first middleware.
"""

from __future__ import annotations

import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize OpenTelemetry before Django app is fully loaded.
# This ensures instrumentation patches are applied before any imports
# in Django's startup sequence could skip them.
if settings.OTEL_ENABLED:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.celery import CeleryInstrumentor
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            SERVICE_VERSION: settings.OTEL_SERVICE_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument all supported libraries
    DjangoInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    CeleryInstrumentor().instrument()

application = get_wsgi_application()
