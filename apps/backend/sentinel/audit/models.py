"""
Audit Event Model.

The immutable core of Sentinel. Every security-relevant action in the platform
produces an AuditEvent record. This is the permanent, tamper-evident record
of what happened, when, and by whom.

IMMUTABILITY CONTRACT:
    AuditEvent records are NEVER updated or deleted at the application layer.
    The AuditEventRepository raises NotImplementedError on update/delete.
    The model has no updated_at field — there is no valid state change.

    Enforcement layers:
    1. Application: Repository raises NotImplementedError
    2. Database: No UPDATE/DELETE grants for the app DB user (production)
    3. Signature: HMAC-SHA256 over key fields detects tampering post-facto

SIGNATURE SCHEME:
    signature = HMAC-SHA256(
        key=settings.SECRET_KEY,
        msg=f"{id}|{event_type}|{actor_id}|{created_at.isoformat()}|{payload_hash}"
    )
    payload_hash = SHA256(json.dumps(payload, sort_keys=True))

    Verification: recompute signature and compare. Mismatch = tampered record.

SCHEMA DESIGN (for future partitioning):
    - id: UUID (non-enumerable, distributed-safe)
    - created_at: the future partition key (range by month)
    - No updated_at (append-only — no updates ever)
    - actor_id: nullable (failed logins have no authenticated actor)
"""

from __future__ import annotations

import uuid

from django.db import models


class AuditEventType(models.TextChoices):
    # Authentication
    USER_LOGIN = "USER_LOGIN", "User Login"
    USER_LOGOUT = "USER_LOGOUT", "User Logout"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED", "User Login Failed"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED", "Password Reset Requested"
    PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED", "Password Reset Completed"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Password Changed"

    # User management
    USER_CREATED = "USER_CREATED", "User Created"
    USER_DEACTIVATED = "USER_DEACTIVATED", "User Deactivated"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED", "User Role Changed"

    # API keys (Phase 3)
    API_KEY_CREATED = "API_KEY_CREATED", "API Key Created"
    API_KEY_ROTATED = "API_KEY_ROTATED", "API Key Rotated"
    API_KEY_REVOKED = "API_KEY_REVOKED", "API Key Revoked"

    # Financial actions (platform-agnostic)
    TRANSFER_INITIATED = "TRANSFER_INITIATED", "Transfer Initiated"
    TRANSFER_APPROVED = "TRANSFER_APPROVED", "Transfer Approved"
    TRANSFER_REJECTED = "TRANSFER_REJECTED", "Transfer Rejected"

    # System
    ADMIN_ACTION = "ADMIN_ACTION", "Admin Action"
    PERMISSION_CHANGED = "PERMISSION_CHANGED", "Permission Changed"
    WEBHOOK_DELIVERED = "WEBHOOK_DELIVERED", "Webhook Delivered"
    WEBHOOK_FAILED = "WEBHOOK_FAILED", "Webhook Failed"


class AuditEvent(models.Model):
    """
    Immutable audit event record.

    Once created, this record must never be modified.
    See module docstring for the full immutability contract.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # WHO performed the action
    actor_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="UUID of the authenticated user who performed this action. "
                  "Null for unauthenticated events (e.g. failed login attempts).",
    )
    actor_email = models.EmailField(
        blank=True,
        default="",
        help_text="Email snapshot at time of event. Denormalized for audit integrity — "
                  "the user's email may change after the event.",
    )
    actor_role = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Role snapshot at time of event.",
    )
    actor_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the actor at time of event.",
    )

    # WHAT happened
    event_type = models.CharField(
        max_length=64,
        choices=AuditEventType.choices,
        db_index=True,
        help_text="Categorized event type from AuditEventType enum.",
    )

    # WHAT was affected
    resource_type = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="Type of the affected resource (e.g. 'user', 'api_key', 'transfer').",
    )
    resource_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="Identifier of the affected resource.",
    )

    # Context and payload
    metadata = models.JSONField(
        default=dict,
        help_text="Structured context for this event. Schema varies by event_type.",
    )
    request_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text="X-Request-ID of the HTTP request that produced this event.",
    )

    # Tamper evidence
    signature = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="HMAC-SHA256 signature over key event fields. Used for tamper detection.",
    )

    # WHEN it happened (partition key candidate)
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="UTC timestamp when this event was recorded. Immutable.",
    )

    class Meta:
        db_table = "audit_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor_id", "created_at"], name="idx_audit_actor_time"),
            models.Index(fields=["event_type", "created_at"], name="idx_audit_type_time"),
            models.Index(fields=["resource_type", "resource_id"], name="idx_audit_resource"),
            models.Index(fields=["request_id"], name="idx_audit_request_id"),
        ]
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"

    def __str__(self) -> str:
        return f"AuditEvent({self.event_type}, actor={self.actor_email}, {self.created_at})"

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} type={self.event_type}>"
