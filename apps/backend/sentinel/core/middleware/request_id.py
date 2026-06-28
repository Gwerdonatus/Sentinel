"""
Request ID Middleware.

Assigns a unique UUID to every incoming request and propagates it:
- In the request object as `request.request_id`
- In the response as `X-Request-ID` header
- In all structlog log records for the duration of the request

This is the foundation for log correlation and incident investigation.
Every support ticket, every error response, every audit record can
reference a request_id to reconstruct exactly what happened.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog
from django.conf import settings
from django.http import HttpRequest, HttpResponse

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class RequestIDMiddleware:
    """Inject a unique request ID into every request lifecycle."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.header_name = getattr(settings, "SENTINEL_REQUEST_ID_HEADER", "X-Request-ID")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Accept an incoming request ID (from upstream proxy) or generate one.
        # This allows tracing across service boundaries when a gateway passes
        # the ID forward.
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        request.request_id = request_id  # type: ignore[attr-defined]

        # Bind to structlog context so all logs within this request include it
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = self.get_response(request)

        # Return the request ID to the client so they can reference it
        response[self.header_name] = request_id

        # Clear structlog context after response to avoid leaking between requests
        structlog.contextvars.unbind_contextvars("request_id")

        return response
