"""
Unit Tests — Exception Hierarchy.

Tests the Sentinel exception base classes and their serialization.
Pure unit tests — no database or HTTP required.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest

from sentinel.core.exceptions.base import (
    SentinelAuthenticationError,
    SentinelConflictError,
    SentinelException,
    SentinelNotFoundError,
    SentinelPermissionError,
    SentinelRateLimitError,
    SentinelServiceUnavailableError,
    SentinelValidationError,
)


class TestSentinelException:
    """Tests for the base SentinelException."""

    def test_default_message_is_used_when_none_provided(self) -> None:
        exc = SentinelException()
        assert exc.message == "An error occurred."

    def test_custom_message_overrides_default(self) -> None:
        exc = SentinelException("Custom error message.")
        assert exc.message == "Custom error message."

    def test_default_code_is_sentinel_error(self) -> None:
        exc = SentinelException()
        assert exc.code == "sentinel_error"

    def test_custom_code_overrides_default(self) -> None:
        exc = SentinelException(code="custom_code")
        assert exc.code == "custom_code"

    def test_details_defaults_to_empty_dict(self) -> None:
        exc = SentinelException()
        assert exc.details == {}

    def test_details_are_stored(self) -> None:
        exc = SentinelException(details={"field": "actor_id", "reason": "required"})
        assert exc.details == {"field": "actor_id", "reason": "required"}

    def test_to_dict_returns_nested_error_structure(self) -> None:
        exc = SentinelException("Something went wrong.", code="test_error")
        result = exc.to_dict()
        assert "error" in result
        assert result["error"]["code"] == "test_error"
        assert result["error"]["message"] == "Something went wrong."

    def test_to_dict_excludes_details_when_empty(self) -> None:
        exc = SentinelException()
        result = exc.to_dict()
        assert "details" not in result["error"]

    def test_to_dict_includes_details_when_set(self) -> None:
        exc = SentinelException(details={"field": "email"})
        result = exc.to_dict()
        assert result["error"]["details"] == {"field": "email"}

    def test_is_subclass_of_exception(self) -> None:
        exc = SentinelException()
        assert isinstance(exc, Exception)

    def test_str_representation_is_message(self) -> None:
        exc = SentinelException("My error message.")
        assert str(exc) == "My error message."


class TestSentinelNotFoundError:
    def test_http_status_is_404(self) -> None:
        assert SentinelNotFoundError.http_status == HTTPStatus.NOT_FOUND

    def test_default_code_is_not_found(self) -> None:
        exc = SentinelNotFoundError()
        assert exc.code == "not_found"

    def test_custom_message(self) -> None:
        exc = SentinelNotFoundError("Event abc-123 not found.")
        assert exc.message == "Event abc-123 not found."


class TestSentinelValidationError:
    def test_http_status_is_422(self) -> None:
        assert SentinelValidationError.http_status == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_default_code_is_validation_error(self) -> None:
        exc = SentinelValidationError()
        assert exc.code == "validation_error"


class TestSentinelPermissionError:
    def test_http_status_is_403(self) -> None:
        assert SentinelPermissionError.http_status == HTTPStatus.FORBIDDEN

    def test_default_code_is_permission_denied(self) -> None:
        exc = SentinelPermissionError()
        assert exc.code == "permission_denied"


class TestSentinelAuthenticationError:
    def test_http_status_is_401(self) -> None:
        assert SentinelAuthenticationError.http_status == HTTPStatus.UNAUTHORIZED

    def test_default_code_is_authentication_required(self) -> None:
        exc = SentinelAuthenticationError()
        assert exc.code == "authentication_required"


class TestSentinelConflictError:
    def test_http_status_is_409(self) -> None:
        assert SentinelConflictError.http_status == HTTPStatus.CONFLICT


class TestSentinelRateLimitError:
    def test_http_status_is_429(self) -> None:
        assert SentinelRateLimitError.http_status == HTTPStatus.TOO_MANY_REQUESTS

    def test_default_code_is_rate_limit_exceeded(self) -> None:
        exc = SentinelRateLimitError()
        assert exc.code == "rate_limit_exceeded"


class TestSentinelServiceUnavailableError:
    def test_http_status_is_503(self) -> None:
        assert SentinelServiceUnavailableError.http_status == HTTPStatus.SERVICE_UNAVAILABLE


class TestExceptionHierarchy:
    """Tests that verify all exceptions inherit correctly."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            SentinelNotFoundError,
            SentinelValidationError,
            SentinelPermissionError,
            SentinelAuthenticationError,
            SentinelConflictError,
            SentinelRateLimitError,
            SentinelServiceUnavailableError,
        ],
    )
    def test_all_exceptions_inherit_from_sentinel_exception(
        self, exc_class: type[SentinelException]
    ) -> None:
        exc = exc_class()
        assert isinstance(exc, SentinelException)
        assert isinstance(exc, Exception)

    @pytest.mark.parametrize(
        "exc_class",
        [
            SentinelNotFoundError,
            SentinelValidationError,
            SentinelPermissionError,
            SentinelAuthenticationError,
            SentinelConflictError,
            SentinelRateLimitError,
            SentinelServiceUnavailableError,
        ],
    )
    def test_all_exceptions_have_valid_http_status(
        self, exc_class: type[SentinelException]
    ) -> None:
        assert exc_class.http_status >= 400
        assert exc_class.http_status < 600
