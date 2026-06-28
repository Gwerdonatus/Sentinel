"""
Unit Tests — RequestID Middleware.

Tests request ID injection, propagation, and response header behavior.
Uses Django's test request factory — no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from sentinel.core.middleware.request_id import RequestIDMiddleware


@pytest.fixture
def factory() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def simple_response_middleware() -> RequestIDMiddleware:
    """Middleware wrapping a simple 200 OK response."""
    def get_response(request: object) -> HttpResponse:
        return HttpResponse("OK")

    return RequestIDMiddleware(get_response)


class TestRequestIDMiddleware:
    def test_generates_request_id_when_not_provided(
        self, factory: RequestFactory, simple_response_middleware: RequestIDMiddleware
    ) -> None:
        request = factory.get("/api/v1/")
        simple_response_middleware(request)
        assert hasattr(request, "request_id")
        # Verify it's a valid UUID
        uuid.UUID(request.request_id)  # type: ignore[attr-defined]

    def test_propagates_incoming_request_id(
        self, factory: RequestFactory, simple_response_middleware: RequestIDMiddleware
    ) -> None:
        existing_id = str(uuid.uuid4())
        request = factory.get("/api/v1/", HTTP_X_REQUEST_ID=existing_id)
        simple_response_middleware(request)
        assert request.request_id == existing_id  # type: ignore[attr-defined]

    def test_adds_request_id_to_response_header(
        self, factory: RequestFactory, simple_response_middleware: RequestIDMiddleware
    ) -> None:
        request = factory.get("/api/v1/")
        response = simple_response_middleware(request)
        assert "X-Request-ID" in response
        # The response header should match what was set on the request
        assert response["X-Request-ID"] == request.request_id  # type: ignore[attr-defined]

    def test_different_requests_get_different_ids(
        self, factory: RequestFactory, simple_response_middleware: RequestIDMiddleware
    ) -> None:
        request1 = factory.get("/api/v1/")
        request2 = factory.get("/api/v1/")
        simple_response_middleware(request1)
        simple_response_middleware(request2)
        assert request1.request_id != request2.request_id  # type: ignore[attr-defined]

    def test_binds_request_id_to_structlog_context(
        self, factory: RequestFactory
    ) -> None:
        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            def get_response(request: object) -> HttpResponse:
                return HttpResponse("OK")

            middleware = RequestIDMiddleware(get_response)
            request = factory.get("/api/v1/")
            middleware(request)

            # Verify structlog was called with request_id
            bind_calls = mock_bind.call_args_list
            bound_keys = {k for call in bind_calls for k in call.kwargs}
            assert "request_id" in bound_keys

    def test_clears_structlog_context_after_response(
        self, factory: RequestFactory
    ) -> None:
        with patch("structlog.contextvars.unbind_contextvars") as mock_unbind:
            def get_response(request: object) -> HttpResponse:
                return HttpResponse("OK")

            middleware = RequestIDMiddleware(get_response)
            request = factory.get("/api/v1/")
            middleware(request)

            mock_unbind.assert_called_once_with("request_id")

    def test_generates_valid_uuid4(
        self, factory: RequestFactory, simple_response_middleware: RequestIDMiddleware
    ) -> None:
        request = factory.get("/api/v1/")
        simple_response_middleware(request)
        parsed = uuid.UUID(request.request_id, version=4)  # type: ignore[attr-defined]
        assert parsed.version == 4

    def test_accepts_custom_header_name(
        self, factory: RequestFactory
    ) -> None:
        custom_id = str(uuid.uuid4())

        def get_response(request: object) -> HttpResponse:
            return HttpResponse("OK")

        with patch("django.conf.settings") as mock_settings:
            mock_settings.SENTINEL_REQUEST_ID_HEADER = "X-Correlation-ID"
            middleware = RequestIDMiddleware(get_response)
            middleware.header_name = "X-Correlation-ID"

            request = factory.get("/api/v1/", HTTP_X_CORRELATION_ID=custom_id)
            response = middleware(request)
            assert request.request_id == custom_id  # type: ignore[attr-defined]
