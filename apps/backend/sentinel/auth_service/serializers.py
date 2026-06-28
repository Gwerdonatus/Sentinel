"""
Auth Service Serializers.

Input validation only — no business logic.
All logic lives in AuthService.
"""

from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from sentinel.auth_service.models import Role, SentinelUser


class UserRegistrationSerializer(serializers.Serializer):
    """Validate user registration input."""

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=12,
        style={"input_type": "password"},
    )
    full_name = serializers.CharField(max_length=255, required=False, default="")
    role = serializers.ChoiceField(
        choices=Role.choices,
        default=Role.VIEWER,
        required=False,
    )

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if SentinelUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value


class LoginSerializer(serializers.Serializer):
    """Validate login credentials."""

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class TokenRefreshSerializer(serializers.Serializer):
    """Validate refresh token input."""

    refresh = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    """Validate logout input — requires refresh token to blacklist it."""

    refresh = serializers.CharField()


class PasswordChangeSerializer(serializers.Serializer):
    """Validate password change request."""

    current_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=12,
        style={"input_type": "password"},
    )

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value


class UserResponseSerializer(serializers.ModelSerializer):
    """Serialize user data for API responses. Never includes password fields."""

    class Meta:
        model = SentinelUser
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "last_login",
            "last_login_ip",
            "must_change_password",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TokenPairResponseSerializer(serializers.Serializer):
    """Serialize JWT token pair response."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    token_type = serializers.CharField(default="Bearer")
    expires_in = serializers.IntegerField(help_text="Access token lifetime in seconds.")
    user = UserResponseSerializer()
