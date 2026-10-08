"""
Risk Intelligence Service.

Orchestrates the full risk pipeline for a single audit event:
  1. Score the event (composite risk signals)
  2. Persist the score back onto the audit event
  3. Evaluate all active alert rules against the scored event
  4. Create Alert records for any matching rules (respecting suppression window)
  5. Dispatch notification tasks for each new alert

This service is called by the Kafka risk consumer. Reprocessing an event is safe:
the score is overwritten and rule/event uniqueness prevents duplicate alerts.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import structlog
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from sentinel.risk.engine import RiskEngine, RiskScore
from sentinel.risk.evaluator import evaluate_rule

if TYPE_CHECKING:
    from sentinel.audit.models import AuditEvent
    from sentinel.risk.models import AlertRule

logger = structlog.get_logger(__name__)


class RiskService:
    """Orchestrates risk scoring and alert creation for audit events."""

    def __init__(self, engine: RiskEngine | None = None) -> None:
        self._engine = engine or RiskEngine()

    def process_event(self, event_id: str) -> RiskScore | None:
        """
        Full risk pipeline for one audit event.

        Loads the event, scores it, persists score, evaluates rules, creates alerts.
        Returns the RiskScore (or None if the event is not found).
        """
        from sentinel.audit.models import AuditEvent

        try:
            event = AuditEvent.objects.get(id=event_id)
        except AuditEvent.DoesNotExist:
            logger.warning("risk_event_not_found", event_id=event_id)
            return None

        # Score the event
        risk_score = self._engine.score(event)

        # Persist score onto the audit event
        # We use update() directly to bypass the immutability guard on the service
        # layer — risk_score is a system-computed field added after creation,
        # not a user-modifiable field. This is documented as the sole exception.
        AuditEvent.objects.filter(id=event.id).update(risk_score=risk_score.score)
        event.risk_score = risk_score.score

        if risk_score.is_elevated:
            self._evaluate_and_alert(event, risk_score)

        return risk_score

    def _evaluate_and_alert(
        self,
        event: "AuditEvent",
        risk_score: RiskScore,  # noqa: F821
    ) -> None:
        """Evaluate active alert rules and create Alert records for matches."""
        from sentinel.risk.models import Alert, AlertRule

        active_rules = AlertRule.objects.filter(is_active=True).select_related("created_by")

        for rule in active_rules:
            if not evaluate_rule(rule, event, risk_score.level):
                continue

            # Duplicate suppression — skip if same rule+actor fired recently
            if self._is_suppressed(rule, event):
                logger.info(
                    "alert_suppressed",
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    actor_id=str(event.actor_id),
                    agent_name=event.agent_name,
                )
                continue

            with transaction.atomic():
                alert, created = Alert.objects.get_or_create(
                    rule=rule,
                    audit_event_id=event.id,
                    defaults={
                        "tenant_id": event.tenant_id,
                        "severity": rule.severity,
                        "actor_id": event.actor_id,
                        "actor_type": getattr(event, "actor_type", "HUMAN"),
                        "actor_email": event.actor_email,
                        "agent_name": getattr(event, "agent_name", ""),
                        "risk_score": risk_score.score,
                        "risk_level": risk_score.level,
                        "risk_explanation": risk_score.explanation,
                    },
                )

                if not created:
                    logger.info(
                        "alert_already_exists",
                        alert_id=str(alert.id),
                        rule_name=rule.name,
                        event_id=str(event.id),
                    )
                    continue

                # Increment rule trigger count
                AlertRule.objects.filter(id=rule.id).update(trigger_count=F("trigger_count") + 1)

            logger.info(
                "alert_created",
                alert_id=str(alert.id),
                rule_name=rule.name,
                severity=alert.severity,
                risk_score=risk_score.score,
                actor_type=alert.actor_type,
                agent_name=alert.agent_name or None,
            )

            # Dispatch notifications asynchronously
            if rule.notification_channels:
                from sentinel.notifications.tasks import dispatch_alert_notifications_task

                dispatch_alert_notifications_task.delay(str(alert.id))

    @staticmethod
    def _is_suppressed(
        rule: "AlertRule",
        event: "AuditEvent",  # noqa: F821
    ) -> bool:
        """Check if a duplicate alert for this rule+actor exists within the suppression window."""
        from sentinel.risk.models import Alert, AlertStatus

        if rule.suppression_window_minutes == 0:
            return False

        cutoff = timezone.now() - timedelta(minutes=rule.suppression_window_minutes)
        return Alert.objects.filter(
            rule=rule,
            actor_id=event.actor_id,
            created_at__gte=cutoff,
            status__in=[AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED],
        ).exists()
