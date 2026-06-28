"""
Trace Context Middleware.

Propagates W3C Trace Context headers (traceparent, tracestate) and binds
the current trace ID to the structlog context.

This ensures that:
1. Distributed traces span across service boundaries correctly
2. Every log line includes the trace_id for correlation with Jaeger/Tempo
3. Error responses include the trace_id for cross-referencing

See: https://www.w3.org/TR/trace-context/
"""

from __future__ import annotations

from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse
from opentelemetry import trace

logger = structlog.get_logger(__name__)


class TraceContextMiddleware:
    """Bind the current OpenTelemetry trace ID to the structlog context."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Get the current span — OpenTelemetry Django instrumentation
        # will have already created a span for this request via
        # DjangoInstrumentor if OTEL is enabled.
        span = trace.get_current_span()
        span_context = span.get_span_context()

        if span_context.is_valid:
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")

            # Bind to structlog so all log lines include these IDs
            structlog.contextvars.bind_contextvars(
                trace_id=trace_id,
                span_id=span_id,
            )

            # Expose in response header for client-side correlation
            response = self.get_response(request)
            response["X-Trace-ID"] = trace_id
        else:
            response = self.get_response(request)

        structlog.contextvars.unbind_contextvars("trace_id", "span_id")

        return response
