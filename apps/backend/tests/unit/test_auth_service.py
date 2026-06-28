"""
Unit Tests — Auth Service.

Tests business logic in isolation. No real DB, no real Redis.
All dependencies mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from sentinel.auth_service.models import Role, SentinelUser
from sentinel.auth_service.services import AuthService
from sentinel.core.exceptions.base import (
    SentinelAuthenticationError,
    SentinelPermissionError,
    SentinelValidationError,
)


def make_user(**kwargs: object) -> SentinelUser:
    """Build an unsaved SentinelUser for testing."""
    user = SentinelUser()
    user.id = kwargs.get("id", uuid4())
    user.email = kwargs.get("email", "test@sentinel.io")
    user.role = kwargs.get("role", Role.VIEWER)
    user.is_active = kwargs.get("is_active", True)
    user.must_change_password = kwargs.get("must_change_password", False)
    user.full_name = kwargs.get("full_name", "Test User")
    return user


class TestAuthServiceRegister:
    def test_viewer_can_self_register(self) -> None:
        mock_repo = MagicMock()
        mock_repo.create.return_value = make_user(role=Role.VIEWER)
        service = AuthService(repository=mock_repo)

        result = service.register(
            email="new@sentinel.io",
            password="SecurePassword123!",
            role="VIEWER",
            requesting_user=None,
        )

        mock_repo.create.assert_called_once()
        assert result.role == Role.VIEWER

    def test_non_admin_cannot_create_admin_user(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        analyst = make_user(role=Role.ANALYST)

        with pytest.raises(SentinelPermissionError):
            service.register(
                email="new@sentinel.io",
                password="SecurePassword123!",
                role="ADMIN",
                requesting_user=analyst,
            )

        mock_repo.create.assert_not_called()

    def test_anonymous_cannot_create_elevated_role(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)

        with pytest.raises(SentinelPermissionError):
            service.register(
                email="new@sentinel.io",
                password="SecurePassword123!",
                role="AUDITOR",
                requesting_user=None,
            )

    def test_admin_can_create_any_role(self) -> None:
        mock_repo = MagicMock()
        mock_repo.create.return_value = make_user(role=Role.AUDITOR)
        service = AuthService(repository=mock_repo)
        admin = make_user(role=Role.ADMIN)

        result = service.register(
            email="auditor@sentinel.io",
            password="SecurePassword123!",
            role="AUDITOR",
            requesting_user=admin,
        )

        mock_repo.create.assert_called_once()


class TestAuthServiceLogin:
    def test_inactive_user_cannot_login(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)

        with patch("sentinel.auth_service.services.authenticate", return_value=None):
            with pytest.raises(SentinelAuthenticationError):
                service.login(email="test@sentinel.io", password="password")

    def test_must_change_password_blocks_login(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        user = make_user(must_change_password=True)

        with patch("sentinel.auth_service.services.authenticate", return_value=user):
            with pytest.raises(SentinelAuthenticationError) as exc_info:
                service.login(email="test@sentinel.io", password="password")

        assert exc_info.value.code == "password_change_required"

    def test_wrong_password_raises_auth_error(self) -> None:
        mock_repo = MagicMock()
        from sentinel.core.exceptions.base import SentinelNotFoundError
        mock_repo.get_by_email.side_effect = SentinelNotFoundError()
        service = AuthService(repository=mock_repo)

        with patch("sentinel.auth_service.services.authenticate", return_value=None):
            with pytest.raises(SentinelAuthenticationError) as exc_info:
                service.login(email="wrong@sentinel.io", password="wrong")

        # Must not reveal whether email exists
        assert "Invalid credentials" in exc_info.value.message

    def test_successful_login_returns_token_dict(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        user = make_user()

        with patch("sentinel.auth_service.services.authenticate", return_value=user), \
             patch.object(service, "_issue_token_pair") as mock_issue:
            mock_issue.return_value = {
                "access": "access.token",
                "refresh": "refresh.token",
                "token_type": "Bearer",
                "expires_in": 900,
                "user": user,
            }
            result = service.login(email="test@sentinel.io", password="correct")

        assert "access" in result
        assert "refresh" in result
        assert result["token_type"] == "Bearer"


class TestAuthServicePasswordChange:
    def test_wrong_current_password_raises(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        user = make_user()
        user.check_password = MagicMock(return_value=False)

        with pytest.raises(SentinelValidationError) as exc_info:
            service.change_password(user, "wrong_current", "NewPassword123!")

        assert "Current password" in exc_info.value.message

    def test_same_password_raises(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        user = make_user()
        user.check_password = MagicMock(return_value=True)

        with pytest.raises(SentinelValidationError) as exc_info:
            service.change_password(user, "SamePass123!", "SamePass123!")

        assert "differ" in exc_info.value.message

    def test_successful_change_saves_user(self) -> None:
        mock_repo = MagicMock()
        service = AuthService(repository=mock_repo)
        user = make_user()
        user.check_password = MagicMock(return_value=True)
        user.set_password = MagicMock()
        user.save = MagicMock()

        service.change_password(user, "OldPass123!", "NewPass456!")

        user.set_password.assert_called_once_with("NewPass456!")
        user.save.assert_called_once()


class TestAuthServiceBlacklist:
    def test_blacklisted_jti_is_detected(self) -> None:
        with patch("sentinel.auth_service.services.cache") as mock_cache:
            mock_cache.get.return_value = "1"
            result = AuthService._is_blacklisted("some-jti")
            assert result is True

    def test_non_blacklisted_jti_returns_false(self) -> None:
        with patch("sentinel.auth_service.services.cache") as mock_cache:
            mock_cache.get.return_value = None
            result = AuthService._is_blacklisted("clean-jti")
            assert result is False

    def test_blacklist_sets_cache_with_ttl(self) -> None:
        with patch("sentinel.auth_service.services.cache") as mock_cache:
            AuthService._blacklist_jti("some-jti", ttl_seconds=3600)
            mock_cache.set.assert_called_once_with(
                "sentinel:jwt:blacklist:some-jti", "1", timeout=3600
            )
