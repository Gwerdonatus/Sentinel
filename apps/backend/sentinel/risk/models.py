"""
Alert Rule and Alert Models.

AlertRule: A stored condition that fires when an audit event matches.
Alert: A fired instance of a rule — the actionable record.

RULE CONDITION FORMAT:
    Conditions are stored as structured JSON, evaluated against AuditEvent fields.

    Simple condition:
        {"field": "risk_score", "operator": "gte", "value": 75}

    Compound condition (AND):
        {
            "operator": "AND",
            "conditions": [
                {"field": "risk_score", "operator": "gte", "value": 50},
                {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"}
            ]
        }

    Supported operators: eq, neq, gt, gte, lt, lte, in, not_in, contains

ALERT LIFECYCLE:
    OPEN → ACKNOWLEDGED → RESOLVED
    OPEN → SUPPRESSED (duplicate suppression window)

BUILT-IN RULES (created by migration):
    - Critical risk score (any actor)
    - AI agent data volume anomaly
    - Impossible travel
    - Off-hours admin action
    - AI agent accessing new resource type
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from sentinel.core.models.base import TimestampedModel


class NotificationChannel(models.TextChoices):
    EMAIL = "email", "Email"
    SLACK = "slack", "Slack Webhook"
    WEBHOOK = "webhook", "Outbound Webhook"
    PAGERDUTY = "pagerduty", "PagerDuty"


class AlertSeverity(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class AlertStatus(models.TextChoices):
    OPEN = "open", "Open"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    RESOLVED = "resolved", "Resolved"
    SUPPRESSED = "suppressed", "Suppressed (duplicate)"


class AlertRule(TimestampedModel):
    """
    A stored rule that fires an Alert when an audit event matches its condition.
    Rules are evaluated against every ingested audit event in near-real-time.
    """

    name = models.CharField(
        max_length=128,
        help_text="Human-readable rule name. e.g. 'Critical risk score — AI agent'",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="What this rule detects and why it matters.",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive rules are not evaluated.",
    )
    is_builtin = models.BooleanField(
        default=False,
        help_text="Built-in rules cannot be deleted, only deactivated.",
    )
    severity = models.CharField(
        max_length=10,
        choices=AlertSeverity.choices,
        default=AlertSeverity.HIGH,
        db_index=True,
    )
    condition = models.JSONField(
        help_text=(
            "Structured condition evaluated against AuditEvent fields. "
            'e.g. {"field": "risk_score", "operator": "gte", "value": 75}'
        ),
    )
    notification_channels = models.JSONField(
        default=list,
        help_text="List of channels to notify: ['email', 'slack', 'webhook']",
    )
    notification_config = models.JSONField(
        default=dict,
        help_text=(
            "Channel-specific configuration. "
            'e.g. {"slack": {"webhook_url": "https://..."}, "email": {"to": ["..."]}}'
        ),
    )
    # Duplicate suppression — don't re-alert for the same rule+actor within this window
    suppression_window_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Suppress duplicate alerts for the same rule+actor within this many minutes.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_alert_rules",
    )
    trigger_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of times this rule has fired.",
    )

    class Meta:
        db_table = "alert_rules"
        ordering = ["-created_at"]
        verbose_name = "Alert Rule"
        verbose_name_plural = "Alert Rules"

    def __str__(self) -> str:
        return f"AlertRule({self.name}, severity={self.severity}, active={self.is_active})"


class Alert(TimestampedModel):
    """
    A fired alert — an instance of an AlertRule matching an AuditEvent.

    Alerts are the actionable output of the risk engine.
    Every alert links back to the rule that fired it and the event that triggered it.
    """

    rule = models.ForeignKey(
        AlertRule,
        on_delete=models.PROTECT,
        related_name="alerts",
        help_text="The rule that fired this alert.",
    )
    audit_event_id = models.UUIDField(
        db_index=True,
        help_text="ID of the AuditEvent that triggered this alert.",
    )
    severity = models.CharField(
        max_length=10,
        choices=AlertSeverity.choices,
        db_index=True,
        help_text="Severity inherited from the rule at time of firing.",
    )
    status = models.CharField(
        max_length=20,
        choices=AlertStatus.choices,
        default=AlertStatus.OPEN,
        db_index=True,
    )

    # Actor snapshot at time of alert
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_type = models.CharField(max_length=20, blank=True, default="")
    actor_email = models.EmailField(blank=True, default="")
    agent_name = models.CharField(max_length=128, blank=True, default="")

    # Risk context
    risk_score = models.SmallIntegerField(null=True, blank=True)
    risk_level = models.CharField(max_length=10, blank=True, default="")
    risk_explanation = models.TextField(blank=True, default="")

    # Lifecycle
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, default="")

    # Notification tracking
    notifications_sent = models.JSONField(
        default=list,
        help_text="List of notification delivery records.",
    )

    class Meta:
        db_table = "alerts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "severity", "created_at"], name="idx_alert_status_sev"),
            models.Index(fields=["actor_id", "created_at"], name="idx_alert_actor"),
            models.Index(fields=["agent_name", "created_at"], name="idx_alert_agent"),
            models.Index(fields=["rule", "actor_id", "created_at"], name="idx_alert_rule_actor"),
        ]
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"

    def __str__(self) -> str:
        return f"Alert({self.rule.name}, {self.severity}, {self.status})"
