"""
Auth Service Repository.

All database access for the auth domain.
No business logic — only queries and persistence.
"""

from __future__ import annotations

import uuid

from django.db import IntegrityError

from sentinel.auth_service.models import SentinelUser
from sentinel.core.exceptions.base import SentinelConflictError, SentinelNotFoundError


class UserRepository:
    """Data access layer for SentinelUser."""

    def get_by_id(self, user_id: uuid.UUID) -> SentinelUser:
        try:
            return SentinelUser.objects.get(id=user_id, is_active=True)
        except SentinelUser.DoesNotExist:
            raise SentinelNotFoundError(f"User {user_id} not found.")

    def get_by_email(self, email: str) -> SentinelUser:
        try:
            return SentinelUser.objects.get(email=email.lower())
        except SentinelUser.DoesNotExist:
            raise SentinelNotFoundError(f"User with email {email} not found.")

    def get_by_email_active(self, email: str) -> SentinelUser:
        try:
            return SentinelUser.objects.get(email=email.lower(), is_active=True)
        except SentinelUser.DoesNotExist:
            raise SentinelNotFoundError("Invalid credentials.")

    def create(
        self,
        email: str,
        password: str,
        full_name: str = "",
        role: str = "VIEWER",
    ) -> SentinelUser:
        try:
            return SentinelUser.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                role=role,
            )
        except IntegrityError:
            raise SentinelConflictError(f"User with email {email} already exists.")

    def deactivate(self, user: SentinelUser) -> SentinelUser:
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        return user

    def update_role(self, user: SentinelUser, role: str) -> SentinelUser:
        user.role = role
        user.save(update_fields=["role", "updated_at"])
        return user

    def list_active(self) -> "models.QuerySet[SentinelUser]":
        from sentinel.auth_service.models import SentinelUser as M
        return M.objects.filter(is_active=True).order_by("-created_at")
