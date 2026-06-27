"""
Structured Logging Middleware.

Logs every HTTP request and response with structured key-value pairs.
All logs are JSON in production and human-readable in development.

Every log line includes:
- request_id (from RequestIDMiddleware)
- trace_id (from TraceContextMiddleware)
- method, path, status_code, duration_ms
- user_id (if authenticated)
- ip_address

This middleware runs AFTER RequestIDMiddleware and TraceContextMiddleware
to ensure those values are already bound to the structlog context.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class StructuredLoggingMiddleware:
    """Log every HTTP request with structured context."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.perf_counter()

        # Bind request-level context
        user_id = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user_id = str(request.user.pk)

        structlog.contextvars.bind_contextvars(
            method=request.method,
            path=request.path,
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
            user_id=user_id,
        )

        response = self.get_response(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Log at different levels based on status code
        log_fn = logger.info
        if response.status_code >= 500:
            log_fn = logger.error
        elif response.status_code >= 400:
            log_fn = logger.warning

        log_fn(
            "http_request",
            status_code=response.status_code,
            duration_ms=duration_ms,
            content_length=len(response.content) if hasattr(response, "content") else 0,
        )

        structlog.contextvars.unbind_contextvars(
            "method", "path", "ip_address", "user_agent", "user_id"
        )

        return response

    @staticmethod
    def _get_client_ip(request: HttpRequest) -> str:
        """Extract the real client IP, respecting proxy headers."""
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # X-Forwarded-For can be a comma-separated list; the first is the client
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
