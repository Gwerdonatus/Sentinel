"""
API Key Service.

Business logic for API key lifecycle: creation, rotation, and revocation.
Key rotation follows a grace period model — the old key remains valid
for a configurable window so dependent services can update without downtime.
"""

from __future__ import annotations

from datetime import timedelta

import structlog
from django.utils import timezone

from sentinel.api_keys.models import APIKey, ActorType
from sentinel.audit.tasks import record_audit_event_task
from sentinel.core.exceptions.base import (
    SentinelNotFoundError,
    SentinelPermissionError,
    SentinelValidationError,
)

logger = structlog.get_logger(__name__)

# How long an old key stays valid after rotation
DEFAULT_ROTATION_GRACE_HOURS = 24


class APIKeyService:
    """Manages API key lifecycle."""

    def create(
        self,
        name: str,
        actor_type: str,
        scopes: list[str],
        created_by: object,
        environment: str = "live",
        agent_name: str = "",
        agent_version: str = "",
        agent_description: str = "",
        expires_in_days: int | None = None,
    ) -> tuple[APIKey, str]:
        """
        Create a new API key.

        Returns:
            (api_key, full_key) — full_key is shown once and never retrievable again.
        """
        self._validate_scopes(scopes)

        if actor_type == ActorType.AI_AGENT and not agent_name:
            raise SentinelValidationError(
                "agent_name is required when actor_type is AI_AGENT."
            )

        full_key, key_prefix, key_hash = APIKey.generate_key(environment)

        expires_at = None
        if expires_in_days is not None:
            expires_at = timezone.now() + timedelta(days=expires_in_days)

        api_key = APIKey.objects.create(
            name=name,
            actor_type=actor_type,
            environment=environment,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            agent_name=agent_name,
            agent_version=agent_version,
            agent_description=agent_description,
            created_by=created_by,
            expires_at=expires_at,
        )

        logger.info(
            "api_key_created",
            key_id=str(api_key.id),
            name=name,
            actor_type=actor_type,
            agent_name=agent_name or None,
            created_by=str(getattr(created_by, "id", None)),
        )

        record_audit_event_task.delay(
            event_type="API_KEY_CREATED",
            actor_id=str(getattr(created_by, "id", None)),
            actor_email=getattr(created_by, "email", ""),
            actor_role=getattr(created_by, "role", ""),
            resource_type="api_key",
            resource_id=str(api_key.id),
            metadata={
                "key_name": name,
                "actor_type": actor_type,
                "agent_name": agent_name,
                "scopes": scopes,
            },
        )

        return api_key, full_key

    def rotate(
        self,
        key_id: str,
        requesting_user: object,
        grace_hours: int = DEFAULT_ROTATION_GRACE_HOURS,
    ) -> tuple[APIKey, str]:
        """
        Rotate an existing API key.

        Creates a new key with the same configuration.
        The old key remains valid for grace_hours to allow dependent services to update.
        Returns (new_api_key, full_new_key).
        """
        try:
            old_key = APIKey.objects.get(id=key_id, deleted_at__isnull=True)
        except APIKey.DoesNotExist:
            raise SentinelNotFoundError(f"API key {key_id} not found.")

        full_key, key_prefix, key_hash = APIKey.generate_key(old_key.environment)

        new_key = APIKey.objects.create(
            name=old_key.name,
            actor_type=old_key.actor_type,
            environment=old_key.environment,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=old_key.scopes,
            agent_name=old_key.agent_name,
            agent_version=old_key.agent_version,
            agent_description=old_key.agent_description,
            created_by=old_key.created_by,
            expires_at=old_key.expires_at,
            rotated_from=old_key,
        )

        # Set grace period on old key
        old_key.rotation_grace_until = timezone.now() + timedelta(hours=grace_hours)
        old_key.save(update_fields=["rotation_grace_until", "updated_at"])

        logger.info(
            "api_key_rotated",
            old_key_id=str(old_key.id),
            new_key_id=str(new_key.id),
            grace_hours=grace_hours,
        )

        record_audit_event_task.delay(
            event_type="API_KEY_ROTATED",
            actor_id=str(getattr(requesting_user, "id", None)),
            actor_email=getattr(requesting_user, "email", ""),
            actor_role=getattr(requesting_user, "role", ""),
            resource_type="api_key",
            resource_id=str(old_key.id),
            metadata={
                "old_key_id": str(old_key.id),
                "new_key_id": str(new_key.id),
                "grace_hours": grace_hours,
                "agent_name": old_key.agent_name,
            },
        )

        return new_key, full_key

    def revoke(self, key_id: str, requesting_user: object) -> APIKey:
        """Immediately revoke an API key. Soft-deletes the record."""
        try:
            api_key = APIKey.objects.get(id=key_id, deleted_at__isnull=True)
        except APIKey.DoesNotExist:
            raise SentinelNotFoundError(f"API key {key_id} not found.")

        api_key.deleted_at = timezone.now()
        api_key.save(update_fields=["deleted_at", "updated_at"])

        logger.info("api_key_revoked", key_id=str(api_key.id), name=api_key.name)

        record_audit_event_task.delay(
            event_type="API_KEY_REVOKED",
            actor_id=str(getattr(requesting_user, "id", None)),
            actor_email=getattr(requesting_user, "email", ""),
            actor_role=getattr(requesting_user, "role", ""),
            resource_type="api_key",
            resource_id=str(api_key.id),
            metadata={"key_name": api_key.name, "agent_name": api_key.agent_name},
        )

        return api_key

    @staticmethod
    def _validate_scopes(scopes: list[str]) -> None:
        invalid = set(scopes) - set(APIKey.AVAILABLE_SCOPES)
        if invalid:
            raise SentinelValidationError(
                f"Invalid scopes: {', '.join(sorted(invalid))}. "
                f"Available: {', '.join(APIKey.AVAILABLE_SCOPES)}"
            )
