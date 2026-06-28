"""
Sentinel User Model.

Custom AbstractBaseUser with:
- Email as the primary login identifier (not username)
- Role field for RBAC (ADMIN, AUDITOR, ANALYST, VIEWER)
- Security-relevant fields: last_login_ip, failed_login_count, device_fingerprint
- Soft-delete pattern via is_active (Django convention)

WHY AbstractBaseUser and not AbstractUser:
  AbstractUser ships with username, first_name, last_name, groups, user_permissions.
  We don't need username (email is the identifier), and we manage permissions via
  the role field — not Django's group/permission tables. AbstractBaseUser gives us
  a clean slate with only the security-relevant fields we actually need.

WHY email as login field:
  Usernames are harder to keep unique across distributed systems and harder to
  rotate. Email addresses are already unique identifiers most users understand.
  In a B2B security platform, email = identity.

MIGRATION WARNING:
  AUTH_USER_MODEL must be set before any migration runs. This is the first
  migration in the project — changing AUTH_USER_MODEL after migrations exist
  is a painful, error-prone process. This is correct by design.
"""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """
    Sentinel RBAC roles.

    ADMIN   — Full platform access. Can manage users, view all events, configure alerts.
    AUDITOR — Read-only access to all audit events and compliance reports.
    ANALYST — Can view events, run queries, create alert rules. Cannot manage users.
    VIEWER  — Read-only access to dashboards and summary data only.
    """

    ADMIN = "ADMIN", "Administrator"
    AUDITOR = "AUDITOR", "Auditor"
    ANALYST = "ANALYST", "Analyst"
    VIEWER = "VIEWER", "Viewer"


class SentinelUserManager(BaseUserManager["SentinelUser"]):
    """Custom manager — email-first user creation."""

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> "SentinelUser":
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        extra_fields.setdefault("role", Role.VIEWER)
        extra_fields.setdefault("is_active", True)
        user: SentinelUser = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> "SentinelUser":
        extra_fields["role"] = Role.ADMIN
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self.create_user(email, password, **extra_fields)


class SentinelUser(AbstractBaseUser, PermissionsMixin):
    """
    Sentinel platform user.

    Identified by email. Authorization controlled by role.
    All security-relevant events on this model produce audit records.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Primary identifier and login credential.",
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name for audit logs and UI.",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.VIEWER,
        db_index=True,
        help_text="RBAC role governing platform access.",
    )

    # Django admin compatibility
    is_staff = models.BooleanField(
        default=False,
        help_text="Grants access to Django admin. Should only be set for ADMIN role users.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive users cannot authenticate. Use this instead of deletion.",
    )

    # Security audit fields
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the most recent successful login.",
    )
    failed_login_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Consecutive failed login attempts since last success. Reset on login.",
    )
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the password was last changed. Used for forced rotation policies.",
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="Force password change on next login (e.g. after admin reset).",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: ClassVar[SentinelUserManager] = SentinelUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["full_name"]

    class Meta:
        db_table = "sentinel_users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email", "is_active"]),
            models.Index(fields=["role", "is_active"]),
        ]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    def __repr__(self) -> str:
        return f"<SentinelUser id={self.id} email={self.email} role={self.role}>"

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_auditor(self) -> bool:
        return self.role == Role.AUDITOR

    @property
    def is_analyst(self) -> bool:
        return self.role == Role.ANALYST

    @property
    def display_name(self) -> str:
        return self.full_name or self.email.split("@")[0]

    def record_successful_login(self, ip_address: str) -> None:
        """Update security fields after a successful authentication."""
        self.last_login_ip = ip_address
        self.failed_login_count = 0
        self.last_login = timezone.now()
        self.save(update_fields=["last_login_ip", "failed_login_count", "last_login", "updated_at"])

    def record_failed_login(self) -> None:
        """Increment failed login counter."""
        self.failed_login_count += 1
        self.save(update_fields=["failed_login_count", "updated_at"])
