"""
Audit Event Service.

Orchestrates creation of signed, immutable audit events.
Called directly by views (via @audit_action decorator) and by Celery tasks.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from django.conf import settings
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from sentinel.audit.models import ActorType, AuditEvent, AuditOutbox
from sentinel.audit.repositories import AuditEventRepository
from sentinel.audit.signing import compute_event_signature

logger = structlog.get_logger(__name__)


class AuditEventService:
    """Service for recording and querying the audit ledger."""

    def __init__(self, repository: AuditEventRepository | None = None) -> None:
        self._repo = repository or AuditEventRepository()

    def record(
        self,
        event_type: str,
        actor_id: str | None = None,
        actor_type: str = ActorType.HUMAN,
        actor_email: str = "",
        actor_role: str = "",
        actor_ip: str = "",
        agent_name: str = "",
        tenant_id: uuid.UUID | None = None,
        resource_type: str = "",
        resource_id: str = "",
        metadata: dict[str, object] | None = None,
        request_id: str = "",
        created_at: datetime | None = None,
    ) -> AuditEvent:
        """
        Record an immutable audit event.

        Computes the HMAC-SHA256 signature before persisting.
        Raises on any persistence failure — callers should handle this
        gracefully (log and continue) unless audit is a hard requirement.
        """
        if metadata is None:
            metadata = {}

        # Generate ID upfront so it's included in the signature
        event_id = uuid.uuid4()
        created_at = created_at or timezone.now()

        signature_version = 2
        signature = compute_event_signature(
            event_id=event_id,
            event_type=event_type,
            actor_id=actor_id,
            actor_email=actor_email,
            created_at=created_at,
            metadata=metadata,
            secret_key=settings.SECRET_KEY,
            version=signature_version,
            tenant_id=str(tenant_id) if tenant_id else None,
            actor_type=actor_type,
            actor_role=actor_role,
            actor_ip=actor_ip,
            agent_name=agent_name,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
        )

        with transaction.atomic():
            event = self._repo.create(
                event_id=event_id,
                created_at=created_at,
                tenant_id=tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                actor_email=actor_email,
                actor_role=actor_role,
                actor_ip=actor_ip,
                agent_name=agent_name,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
                request_id=request_id,
                signature=signature,
                signature_version=signature_version,
            )
            AuditOutbox.objects.create(audit_event=event)

        logger.info(
            "audit_event_recorded",
            event_id=str(event.id),
            event_type=event_type,
            actor_id=actor_id,
            actor_email=actor_email,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
        )

        return event

    def get(self, event_id: uuid.UUID) -> AuditEvent:
        return self._repo.get_by_id(event_id)

    def list(
        self,
        *,
        actor_id: uuid.UUID | None = None,
        actor_type: str | None = None,
        agent_name: str | None = None,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> QuerySet[AuditEvent]:
        return self._repo.list(
            actor_id=actor_id,
            actor_type=actor_type,
            agent_name=agent_name,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            from_dt=from_dt,
            to_dt=to_dt,
        )

    def verify_signature(self, event: AuditEvent) -> bool:
        """
        Verify the HMAC signature of a stored event.
        Returns True if unmodified, False if tampered.
        """
        from sentinel.audit.signing import verify_event_signature

        return verify_event_signature(
            event_id=event.id,
            event_type=event.event_type,
            actor_id=str(event.actor_id) if event.actor_id else None,
            actor_email=event.actor_email,
            created_at=event.created_at,
            metadata=event.metadata,
            stored_signature=event.signature,
            secret_key=settings.SECRET_KEY,
            version=event.signature_version,
            tenant_id=str(event.tenant_id) if event.tenant_id else None,
            actor_type=event.actor_type,
            actor_role=event.actor_role,
            actor_ip=str(event.actor_ip or ""),
            agent_name=event.agent_name,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            request_id=event.request_id,
        )
