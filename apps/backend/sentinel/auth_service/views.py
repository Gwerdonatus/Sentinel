"""
Auth Service Views.

All views are thin — validate input, call service, return response.
No business logic here.

Endpoints:
    POST /api/v1/auth/register/       — create account
    POST /api/v1/auth/login/          — obtain token pair
    POST /api/v1/auth/refresh/        — rotate refresh token
    POST /api/v1/auth/logout/         — blacklist refresh token
    GET  /api/v1/auth/me/             — current user profile
    POST /api/v1/auth/me/password/    — change password
"""

from __future__ import annotations

from typing import Any

import structlog
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentinel.auth_service.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    TokenPairResponseSerializer,
    TokenRefreshSerializer,
    UserRegistrationSerializer,
    UserResponseSerializer,
)
from sentinel.auth_service.services import AuthService

logger = structlog.get_logger(__name__)


class RegisterView(APIView):
    """
    POST /api/v1/auth/register/

    Public endpoint — creates a new VIEWER account.
    ADMIN users can POST with `role` field to create elevated accounts.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        requesting_user = request.user if request.user.is_authenticated else None
        service = AuthService()

        user = service.register(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            full_name=serializer.validated_data.get("full_name", ""),
            role=serializer.validated_data.get("role", "VIEWER"),
            requesting_user=requesting_user,  # type: ignore[arg-type]
        )

        return Response(
            UserResponseSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticate with email and password.
    Returns JWT access + refresh tokens.
    Rate-limited by django-axes (5 failures → 1 hour lockout).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = AuthService()
        ip = request.META.get("REMOTE_ADDR", "")

        result = service.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            ip_address=ip,
        )

        return Response(
            TokenPairResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    """
    POST /api/v1/auth/refresh/

    Exchange a valid refresh token for a new access + refresh token pair.
    The submitted refresh token is immediately blacklisted (rotation).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = AuthService()
        result = service.refresh(serializer.validated_data["refresh"])

        return Response(
            TokenPairResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklist the submitted refresh token.
    The access token remains valid until it expires (15 minutes max).
    Clients should discard both tokens after logout.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = AuthService()
        service.logout(
            refresh_token=serializer.validated_data["refresh"],
            user=request.user,  # type: ignore[arg-type]
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """
    GET /api/v1/auth/me/

    Returns the authenticated user's profile.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(
            UserResponseSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )


class PasswordChangeView(APIView):
    """
    POST /api/v1/auth/me/password/

    Change the authenticated user's password.
    Requires current password verification.
    Invalidates all existing refresh tokens.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = AuthService()
        service.change_password(
            user=request.user,  # type: ignore[arg-type]
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )
