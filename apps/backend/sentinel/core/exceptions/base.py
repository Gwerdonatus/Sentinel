"""
Sentinel Exception Hierarchy.

All domain-specific exceptions inherit from SentinelException.
The DRF exception handler converts these to structured HTTP responses automatically.

Usage:
    raise SentinelNotFoundError(f"Event {event_id} not found")
    raise SentinelValidationError("Actor ID cannot be empty")
    raise SentinelPermissionError("Insufficient permissions to view audit log")

Never raise:
    ValueError, KeyError, or other built-in exceptions for expected error cases.
    These are not caught by the Sentinel exception handler and will produce 500s.
"""

from __future__ import annotations

from http import HTTPStatus


class SentinelException(Exception):
    """Base class for all Sentinel domain exceptions."""

    default_message: str = "An error occurred."
    default_code: str = "sentinel_error"
    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        code: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, object]:
        """Serialize to API error response format."""
        payload: dict[str, object] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details  # type: ignore[index]
        return payload


class SentinelNotFoundError(SentinelException):
    """Raised when a requested resource does not exist."""

    default_message = "Resource not found."
    default_code = "not_found"
    http_status = HTTPStatus.NOT_FOUND


class SentinelValidationError(SentinelException):
    """Raised when input fails business validation after serializer-level validation."""

    default_message = "Validation failed."
    default_code = "validation_error"
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY


class SentinelPermissionError(SentinelException):
    """Raised when a user lacks permission to perform an action."""

    default_message = "Permission denied."
    default_code = "permission_denied"
    http_status = HTTPStatus.FORBIDDEN


class SentinelAuthenticationError(SentinelException):
    """Raised when authentication fails or a token is invalid."""

    default_message = "Authentication required."
    default_code = "authentication_required"
    http_status = HTTPStatus.UNAUTHORIZED


class SentinelConflictError(SentinelException):
    """Raised when an action conflicts with existing state."""

    default_message = "Conflict with current state."
    default_code = "conflict"
    http_status = HTTPStatus.CONFLICT


class SentinelRateLimitError(SentinelException):
    """Raised when a client exceeds their rate limit."""

    default_message = "Rate limit exceeded. Please retry after the indicated time."
    default_code = "rate_limit_exceeded"
    http_status = HTTPStatus.TOO_MANY_REQUESTS


class SentinelServiceUnavailableError(SentinelException):
    """Raised when a downstream dependency is unavailable."""

    default_message = "Service temporarily unavailable."
    default_code = "service_unavailable"
    http_status = HTTPStatus.SERVICE_UNAVAILABLE
