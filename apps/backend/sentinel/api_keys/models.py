"""
API Key Model.

API keys serve two purposes in Sentinel:
1. Human API access (developers integrating with Sentinel's API)
2. Identity for AI agents and services — the mechanism by which
   non-human actors are authenticated and attributed in the audit ledger.

KEY STORAGE:
    The full key is shown ONCE at creation and never stored.
    Storage: prefix (first 8 chars, for lookup) + HMAC-SHA256 hash of full key.
    Verification: hash the presented key, compare to stored hash.
    This means a database breach exposes no usable keys.

KEY FORMAT:
    sk_live_<32 random chars>   — production keys
    sk_test_<32 random chars>   — test/development keys

    The prefix 'sk_live_' or 'sk_test_' is also the lookup prefix stored
    in key_prefix so we can find the right key record without a full table scan.

AI AGENT IDENTITY:
    When actor_type = AI_AGENT, the key carries:
    - agent_name: human-readable name ("support-bot-v2")
    - agent_version: model/version string ("gpt-4-turbo-2024-04")
    - agent_description: what this agent does

    Every audit event produced via this key inherits these fields,
    making AI agent attribution complete and queryable.

SCOPES:
    Keys are scoped to specific permissions. Scopes follow the pattern:
    "<resource>:<action>" — e.g. "events:write", "events:read", "alerts:read"

    An AI agent with "events:write" can ingest audit events but cannot
    read the ledger, manage users, or access risk scores.
"""

from __future__ import annotations

import secrets
import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils import timezone

from sentinel.core.models.base import SoftDeletableModel


class ActorType(models.TextChoices):
    """Who is this key for?"""
    HUMAN_API = "HUMAN_API", "Human Developer API Access"
    SERVICE = "SERVICE", "Backend Service"
    AI_AGENT = "AI_AGENT", "AI Agent"


class KeyEnvironment(models.TextChoices):
    LIVE = "live", "Production"
    TEST = "test", "Test / Development"


class APIKey(SoftDeletableModel):
    """
    API key for service and AI agent authentication.

    The full key value is never stored. Only the prefix and hash are persisted.
    """

    name = models.CharField(
        max_length=128,
        help_text="Human-readable name. e.g. 'Production Support Bot', 'Fraud Detector v3'",
    )
    actor_type = models.CharField(
        max_length=20,
        choices=ActorType.choices,
        default=ActorType.SERVICE,
        db_index=True,
    )
    environment = models.CharField(
        max_length=10,
        choices=KeyEnvironment.choices,
        default=KeyEnvironment.LIVE,
        db_index=True,
    )

    # Key storage — the actual secret is never persisted
    key_prefix = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        help_text="First chars of the key for O(1) lookup. Not secret.",
    )
    key_hash = models.CharField(
        max_length=64,
        help_text="HMAC-SHA256 hash of the full key. Used for verification.",
    )

    # Scopes — what this key is permitted to do
    scopes = models.JSONField(
        default=list,
        help_text=(
            "List of permitted scopes. "
            "e.g. ['events:write', 'events:read', 'alerts:read']. "
            "Empty list = no permissions."
        ),
    )

    # AI agent identity fields (populated when actor_type = AI_AGENT)
    agent_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Machine-readable agent name. e.g. 'support-bot', 'fraud-detector'",
    )
    agent_version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Model or version identifier. e.g. 'gpt-4-turbo-2024-04', 'v2.1.3'",
    )
    agent_description = models.TextField(
        blank=True,
        default="",
        help_text="What this agent does. Used in audit reports and investigation.",
    )

    # Ownership
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_api_keys",
        help_text="User who created this key.",
    )

    # Usage tracking
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key was last used for authentication.",
    )
    last_used_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP from which this key was last used.",
    )
    total_uses = models.PositiveIntegerField(
        default=0,
        help_text="Total number of authenticated requests using this key.",
    )

    # Expiry
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this key expires. Null = never expires.",
    )

    # Rotation tracking
    rotated_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rotated_to",
        help_text="The key this was rotated from, if any.",
    )
    rotation_grace_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Old key remains valid until this time after rotation.",
    )

    AVAILABLE_SCOPES: ClassVar[list[str]] = [
        "events:write",
        "events:read",
        "alerts:read",
        "alerts:write",
        "risks:read",
        "users:read",
        "api_keys:read",
    ]

    class Meta:
        db_table = "api_keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["key_prefix"], name="idx_api_key_prefix"),
            models.Index(fields=["actor_type", "created_at"], name="idx_api_key_actor_type"),
            models.Index(fields=["agent_name"], name="idx_api_key_agent_name"),
        ]
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self) -> str:
        return f"APIKey({self.name}, type={self.actor_type}, prefix={self.key_prefix})"

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_deleted and not self.is_expired

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def record_usage(self, ip_address: str = "") -> None:
        """Update usage tracking fields. Called on every authenticated request."""
        self.last_used_at = timezone.now()
        self.last_used_ip = ip_address or None
        self.total_uses += 1
        self.save(update_fields=["last_used_at", "last_used_ip", "total_uses", "updated_at"])

    @classmethod
    def generate_key(cls, environment: str = "live") -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            (full_key, key_prefix, key_hash)

        The full_key is shown to the user ONCE and never stored.
        Only key_prefix and key_hash are persisted.
        """
        import hashlib
        import hmac

        raw = secrets.token_urlsafe(32)
        full_key = f"sk_{environment}_{raw}"
        key_prefix = full_key[:12]
        key_hash = hmac.new(
            key=settings.SECRET_KEY.encode(),
            msg=full_key.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return full_key, key_prefix, key_hash

    @classmethod
    def verify_key(cls, presented_key: str) -> "APIKey | None":
        """
        Verify a presented API key against stored hashes.

        Returns the matching APIKey if valid and active, None otherwise.
        Uses constant-time comparison to prevent timing attacks.
        """
        import hashlib
        import hmac as hmac_module

        if not presented_key or len(presented_key) < 12:
            return None

        key_prefix = presented_key[:12]
        try:
            api_key = cls.objects.get(key_prefix=key_prefix, deleted_at__isnull=True)
        except cls.DoesNotExist:
            return None

        if not api_key.is_active:
            return None

        expected_hash = hmac_module.new(
            key=settings.SECRET_KEY.encode(),
            msg=presented_key.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if hmac_module.compare_digest(expected_hash, api_key.key_hash):
            return api_key
        return None
