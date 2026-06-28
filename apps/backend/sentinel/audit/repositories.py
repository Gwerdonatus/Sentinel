"""
Audit Event Repository.

Data access layer for the audit ledger. Enforces immutability at the
application layer by raising NotImplementedError on any mutating operation.

This is the first defense in the immutability stack:
    Layer 1: Repository (raises here)
    Layer 2: DB permissions (no UPDATE/DELETE in production)
    Layer 3: Signature verification (detects post-hoc tampering)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from sentinel.audit.models import AuditEvent

if TYPE_CHECKING:
    pass


class AuditEventRepository:
    """
    Append-only repository for audit events.

    Only create() and read operations are permitted.
    update() and delete() raise NotImplementedError unconditionally.
    """

    def create(
        self,
        event_type: str,
        actor_id: str | None,
        actor_email: str,
        actor_role: str,
        actor_ip: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, object],
        request_id: str,
        signature: str,
    ) -> AuditEvent:
        """Create and persist a new audit event. The only write operation."""
        return AuditEvent.objects.create(
            event_type=event_type,
            actor_id=uuid.UUID(actor_id) if actor_id else None,
            actor_email=actor_email,
            actor_role=actor_role,
            actor_ip=actor_ip,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            request_id=request_id,
            signature=signature,
        )

    def get_by_id(self, event_id: uuid.UUID) -> AuditEvent:
        from sentinel.core.exceptions.base import SentinelNotFoundError
        try:
            return AuditEvent.objects.get(id=event_id)
        except AuditEvent.DoesNotExist:
            raise SentinelNotFoundError(f"Audit event {event_id} not found.")

    def list(
        self,
        *,
        actor_id: uuid.UUID | None = None,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        request_id: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> QuerySet[AuditEvent]:
        """
        Return a filtered queryset of audit events.
        All parameters are optional — unfiltered returns all events.
        Caller is responsible for pagination (cursor-based).
        """
        qs = AuditEvent.objects.all()

        if actor_id is not None:
            qs = qs.filter(actor_id=actor_id)
        if event_type is not None:
            qs = qs.filter(event_type=event_type)
        if resource_type is not None:
            qs = qs.filter(resource_type=resource_type)
        if resource_id is not None:
            qs = qs.filter(resource_id=resource_id)
        if request_id is not None:
            qs = qs.filter(request_id=request_id)
        if from_dt is not None:
            qs = qs.filter(created_at__gte=from_dt)
        if to_dt is not None:
            qs = qs.filter(created_at__lte=to_dt)

        return qs.order_by("-created_at")

    def update(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError(
            "AuditEvent records are immutable. Updates are not permitted. "
            "This is enforced at the application layer to protect audit integrity."
        )

    def delete(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError(
            "AuditEvent records are immutable. Deletion is not permitted. "
            "Implement a retention archival strategy instead of deletion."
        )
