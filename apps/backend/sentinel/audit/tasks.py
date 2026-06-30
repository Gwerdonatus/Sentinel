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

        # Trigger risk scoring pipeline for every recorded event
        from sentinel.risk.tasks import score_and_alert_task
        score_and_alert_task.delay(str(event.id))

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
