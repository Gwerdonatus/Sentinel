"""
Auth Service.

Business logic for authentication, JWT token management, and session control.

Token blacklist strategy:
    We blacklist refresh token JTIs in Redis (not the DB simplejwt table).
    Reason: every authenticated request would require a DB lookup to check
    the blacklist — Redis gives O(1) lookup with TTL-based expiry at near-zero
    added latency.

    Key pattern: sentinel:jwt:blacklist:{jti}
    TTL: matches REFRESH_TOKEN_LIFETIME so the key auto-expires when the
    token would have expired anyway.

Refresh token rotation:
    Every use of a refresh token blacklists it and issues a new one.
    If a stolen refresh token is used, the legitimate user's next refresh
    will detect the blacklisted token and force re-authentication.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import structlog
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from sentinel.auth_service.models import SentinelUser
from sentinel.auth_service.repositories import UserRepository
from sentinel.core.exceptions.base import (
    SentinelAuthenticationError,
    SentinelNotFoundError,
    SentinelPermissionError,
    SentinelValidationError,
)

logger = structlog.get_logger(__name__)

# Redis key prefix for blacklisted JTIs
_BLACKLIST_PREFIX = "sentinel:jwt:blacklist:"


class AuthService:
    """Authentication and token lifecycle management."""

    def __init__(self, repository: UserRepository | None = None) -> None:
        self._repo = repository or UserRepository()

    def register(
        self,
        email: str,
        password: str,
        full_name: str = "",
        role: str = "VIEWER",
        requesting_user: SentinelUser | None = None,
    ) -> SentinelUser:
        """
        Register a new user.

        Only ADMIN users can create non-VIEWER accounts.
        Self-registration always creates VIEWER accounts.
        """
        if role != "VIEWER" and (
            requesting_user is None or not requesting_user.is_admin
        ):
            raise SentinelPermissionError(
                "Only administrators can create accounts with elevated roles."
            )

        user = self._repo.create(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
        )

        logger.info(
            "user_registered",
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            created_by=str(getattr(requesting_user, "id", "self")),
        )

        return user

    def login(
        self,
        email: str,
        password: str,
        ip_address: str = "",
    ) -> dict[str, object]:
        """
        Authenticate with email/password.
        Returns access token, refresh token, and user data.
        Raises SentinelAuthenticationError on any failure.
        """
        # authenticate() calls check_password() and runs django-axes checks
        user = authenticate(email=email, password=password)

        if user is None:
            # Try to find user to increment failure counter
            try:
                failed_user = self._repo.get_by_email(email)
                failed_user.record_failed_login()
            except SentinelNotFoundError:
                pass

            logger.warning("login_failed", email=email, ip=ip_address)
            # Deliberately vague — don't reveal whether email exists
            raise SentinelAuthenticationError("Invalid credentials.")

        if not user.is_active:
            raise SentinelAuthenticationError("Account is disabled. Contact your administrator.")

        if user.must_change_password:
            raise SentinelAuthenticationError(
                "Password change required before login.",
                code="password_change_required",
            )

        tokens = self._issue_token_pair(user)

        logger.info(
            "login_success",
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            ip=ip_address,
        )

        return tokens

    def refresh(self, refresh_token: str) -> dict[str, object]:
        """
        Issue a new access/refresh token pair.
        The consumed refresh token is blacklisted immediately.
        """
        try:
            token = RefreshToken(refresh_token)
        except TokenError as e:
            raise SentinelAuthenticationError(f"Invalid refresh token: {e}") from e

        jti: str = str(token["jti"])

        if self._is_blacklisted(jti):
            logger.warning("refresh_token_reuse_detected", jti=jti)
            raise SentinelAuthenticationError(
                "Refresh token has already been used. Please log in again."
            )

        # Blacklist the consumed token before issuing new ones
        self._blacklist_jti(jti, ttl_seconds=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()))

        user_id: str = str(token["user_id"])
        try:
            user = self._repo.get_by_id(uuid.UUID(user_id))
        except (SentinelNotFoundError, ValueError) as e:
            raise SentinelAuthenticationError("User not found.") from e

        return self._issue_token_pair(user)

    def logout(self, refresh_token: str, user: SentinelUser) -> None:
        """
        Invalidate a refresh token on explicit logout.
        Access tokens cannot be revoked (short TTL is the mitigation).
        """
        try:
            token = RefreshToken(refresh_token)
            jti: str = str(token["jti"])
            ttl = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
            self._blacklist_jti(jti, ttl_seconds=ttl)
        except TokenError:
            # Token already invalid — logout is still "successful"
            pass

        logger.info("user_logged_out", user_id=str(user.id), email=user.email)

    def change_password(
        self,
        user: SentinelUser,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change password after verifying the current one.
        Invalidates all existing refresh tokens by updating the user's
        password hash (which is embedded in JWTs via the password hash claim).
        """
        if not user.check_password(current_password):
            raise SentinelValidationError("Current password is incorrect.")

        if current_password == new_password:
            raise SentinelValidationError("New password must differ from current password.")

        user.set_password(new_password)
        user.password_changed_at = timezone.now()
        user.must_change_password = False
        user.save(update_fields=["password", "password_changed_at", "must_change_password", "updated_at"])

        logger.info("password_changed", user_id=str(user.id), email=user.email)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _issue_token_pair(self, user: SentinelUser) -> dict[str, object]:
        """Issue a fresh access/refresh token pair for a user."""
        refresh = RefreshToken.for_user(user)

        # Embed role in the access token so authorization checks don't need DB
        refresh["role"] = user.role
        refresh["email"] = user.email

        access = refresh.access_token
        lifetime: timedelta = settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"]

        return {
            "access": str(access),
            "refresh": str(refresh),
            "token_type": "Bearer",
            "expires_in": int(lifetime.total_seconds()),
            "user": user,
        }

    @staticmethod
    def _blacklist_jti(jti: str, ttl_seconds: int) -> None:
        """Add a JTI to the Redis blacklist with TTL."""
        key = f"{_BLACKLIST_PREFIX}{jti}"
        cache.set(key, "1", timeout=ttl_seconds)

    @staticmethod
    def _is_blacklisted(jti: str) -> bool:
        """Check if a JTI is in the Redis blacklist."""
        key = f"{_BLACKLIST_PREFIX}{jti}"
        return cache.get(key) is not None
