"""
Sentinel DRF Exception Handler.

Converts all exceptions — both Sentinel domain exceptions and DRF exceptions —
into a consistent structured JSON error response format.

All error responses follow this schema:
    {
        "error": {
            "code": "not_found",
            "message": "Event abc123 not found.",
            "request_id": "550e8400-e29b-41d4-a716-446655440000",
            "details": {}  // optional field-level validation errors
        }
    }

Registered in settings.py as REST_FRAMEWORK["EXCEPTION_HANDLER"].
"""

from __future__ import annotations

import structlog
from django.http import HttpRequest
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from sentinel.core.exceptions.base import SentinelException

logger = structlog.get_logger(__name__)


def sentinel_exception_handler(
    exc: Exception,
    context: dict[str, object],
) -> Response | None:
    """
    Global DRF exception handler for Sentinel.

    Handles:
    1. SentinelException subclasses — domain errors with typed HTTP status
    2. DRF APIException subclasses — framework-level errors
    3. All other exceptions — logged as errors and returned as 500

    Returns None for unhandled exceptions (DRF will re-raise them).
    """
    request: HttpRequest | None = context.get("request")  # type: ignore[assignment]
    request_id = getattr(request, "request_id", "unknown") if request else "unknown"

    # --- Sentinel domain exceptions ---
    if isinstance(exc, SentinelException):
        logger.warning(
            "sentinel_exception",
            exception_type=type(exc).__name__,
            exception_code=exc.code,
            exception_message=exc.message,
            request_id=request_id,
        )

        response_data = exc.to_dict()
        response_data["error"]["request_id"] = request_id  # type: ignore[index]

        return Response(
            data=response_data,
            status=exc.http_status,
        )

    # --- DRF exceptions — normalize to Sentinel response format ---
    drf_response = drf_exception_handler(exc, context)

    if drf_response is not None:
        if isinstance(exc, ValidationError):
            code = "validation_error"
            message = "Request validation failed."
            details = drf_response.data
        elif isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            code = "authentication_required"
            message = str(exc.detail)
            details = {}
        elif isinstance(exc, PermissionDenied):
            code = "permission_denied"
            message = str(exc.detail)
            details = {}
        elif isinstance(exc, APIException):
            code = exc.default_code
            message = str(exc.detail)
            details = {}
        else:
            code = "api_error"
            message = "An API error occurred."
            details = {}

        drf_response.data = {
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "details": details,
            }
        }

        return drf_response

    # --- Unhandled exceptions — log and return 500 ---
    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        request_id=request_id,
        exc_info=True,
    )

    return Response(
        data={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please reference the request_id when contacting support.",
                "request_id": request_id,
                "details": {},
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
