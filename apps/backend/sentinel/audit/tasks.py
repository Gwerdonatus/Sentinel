"""
Audit Celery Tasks.

Async audit event recording. HTTP endpoints dispatch tasks so that
audit writes never add latency to the user-facing response.

Reliability note:
    If the Celery worker is down, audit events will be queued in Redis
    and processed when the worker recovers. This means audit records
    arrive slightly late but are never lost (assuming Redis persistence).

    For hard audit requirements (financial regulations), use the
    synchronous AuditEventService.record() instead.
"""

from __future__ import annotations

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="sentinel.audit.record_event",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,  # Only ack after task completes — prevents loss on worker crash
)
def record_audit_event_task(
    self: object,
    event_type: str,
    actor_id: str | None = None,
    actor_email: str = "",
    actor_role: str = "",
    actor_ip: str = "",
    resource_type: str = "",
    resource_id: str | None = None,
    metadata: dict[str, object] | None = None,
    request_id: str = "",
) -> str:
    """
    Record an audit event asynchronously.

    Retries up to 3 times on failure with 5-second delay.
    Returns the string UUID of the created event.
    """
    from sentinel.audit.services import AuditEventService

    try:
        service = AuditEventService()
        event = service.record(
            event_type=event_type,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            actor_ip=actor_ip,
            resource_type=resource_type,
            resource_id=resource_id or "",
            metadata=metadata or {},
            request_id=request_id,
        )

        return str(event.id)

    except Exception as exc:
        logger.error(
            "audit_task_failed",
            event_type=event_type,
            actor_id=actor_id,
            error=str(exc),
            retry_count=self.request.retries,  # type: ignore[union-attr]
        )
        raise self.retry(exc=exc)  # type: ignore[union-attr]


@shared_task(name="sentinel.audit.publish_outbox", bind=True, max_retries=5)
def publish_pending_audit_events_task(self: object, batch_size: int = 100) -> dict[str, int]:
    """Publish pending outbox rows with bounded exponential backoff."""
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from sentinel.audit.models import AuditOutbox
    from sentinel.kafka.producer import publish_audit_event

    published = 0
    failed = 0
    now = timezone.now()
    pending_ids = list(
        AuditOutbox.objects.filter(published_at__isnull=True, next_attempt_at__lte=now)
        .order_by("created_at")
        .values_list("id", flat=True)[:batch_size]
    )

    for outbox_id in pending_ids:
        with transaction.atomic():
            entry = (
                AuditOutbox.objects.select_for_update()
                .select_related("audit_event")
                .get(id=outbox_id)
            )
            if entry.published_at is not None:
                continue
            try:
                publish_audit_event(entry.audit_event)
            except Exception as exc:
                entry.attempts += 1
                delay_seconds = min(300, 2 ** min(entry.attempts, 8))
                entry.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
                entry.last_error = str(exc)[:2000]
                entry.save(update_fields=["attempts", "next_attempt_at", "last_error"])
                failed += 1
                logger.warning(
                    "audit_outbox_publish_failed",
                    outbox_id=str(entry.id),
                    event_id=str(entry.audit_event_id),
                    attempts=entry.attempts,
                    error=str(exc),
                )
            else:
                entry.published_at = timezone.now()
                entry.last_error = ""
                entry.save(update_fields=["published_at", "last_error"])
                published += 1

    return {"published": published, "failed": failed}
