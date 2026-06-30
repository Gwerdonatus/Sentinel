"""
Risk Intelligence Celery Tasks.

Every audit event triggers score_and_alert_task after it is recorded.
The task runs the full risk pipeline: score → alert → notify.

Pipeline latency target: < 500ms P99 for events up to risk_score computation.
Notification delivery is further decoupled into dispatch_alert_notifications_task.
"""

from __future__ import annotations

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="sentinel.risk.score_and_alert",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def score_and_alert_task(self: object, event_id: str) -> dict[str, object]:
    """
    Score an audit event for risk and fire alerts if thresholds are crossed.

    Called automatically after every audit event is recorded.
    Returns a summary dict for monitoring purposes.
    """
    from sentinel.risk.services import RiskService

    try:
        service = RiskService()
        risk_score = service.process_event(event_id)

        if risk_score is None:
            return {"event_id": event_id, "status": "not_found"}

        return {
            "event_id": event_id,
            "score": risk_score.score,
            "level": risk_score.level,
            "fired_signals": risk_score.fired_signals,
        }

    except Exception as exc:
        logger.error(
            "risk_task_failed",
            event_id=event_id,
            error=str(exc),
            retry=self.request.retries,  # type: ignore[union-attr]
        )
        raise self.retry(exc=exc)  # type: ignore[union-attr]
