"""
Notification Delivery Tasks.

Dispatches alert notifications to configured channels.
Each channel is a separate Celery task with independent retry logic.

Channels:
    Slack   — POST to incoming webhook URL
    Email   — Django email backend (SMTP/SendGrid)
    Webhook — POST to any HTTPS URL with HMAC signature header

All delivery tasks:
    - Retry up to 3 times with exponential backoff
    - Record delivery outcome (success/failure) on the Alert record
    - Never crash the risk pipeline — delivery failures are logged and tracked

Configuration per channel is stored in AlertRule.notification_config:
    {
        "slack": {"webhook_url": "https://hooks.slack.com/..."},
        "email": {"to": ["security@company.com", "cto@company.com"]},
        "webhook": {"url": "https://your-system.com/alerts", "secret": "..."}
    }
"""

from __future__ import annotations

import json
import uuid

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="sentinel.notifications.dispatch_alert",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def dispatch_alert_notifications_task(self: object, alert_id: str) -> None:
    """
    Load an alert and dispatch notifications to all configured channels.
    Spawns a sub-task per channel so one failed channel doesn't block others.
    """
    from sentinel.risk.models import Alert

    try:
        alert = Alert.objects.select_related("rule").get(id=uuid.UUID(alert_id))
    except Alert.DoesNotExist:
        logger.error("dispatch_alert_not_found", alert_id=alert_id)
        return

    channels = alert.rule.notification_channels
    config = alert.rule.notification_config

    for channel in channels:
        if channel == "slack":
            deliver_slack_task.delay(alert_id, config.get("slack", {}))
        elif channel == "email":
            deliver_email_task.delay(alert_id, config.get("email", {}))
        elif channel == "webhook":
            deliver_webhook_task.delay(alert_id, config.get("webhook", {}))
        else:
            logger.warning("unknown_notification_channel", channel=channel, alert_id=alert_id)


@shared_task(
    name="sentinel.notifications.deliver_slack",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def deliver_slack_task(
    self: object,
    alert_id: str,
    config: dict[str, object],
) -> None:
    """POST alert summary to a Slack incoming webhook."""
    import urllib.error
    import urllib.request

    from sentinel.risk.models import Alert

    webhook_url = config.get("webhook_url")
    if not webhook_url:
        logger.warning("slack_no_webhook_url", alert_id=alert_id)
        return

    try:
        alert = Alert.objects.select_related("rule").get(id=uuid.UUID(alert_id))
    except Alert.DoesNotExist:
        return

    # Severity → Slack color
    color_map = {
        "critical": "#FF0000",
        "high": "#FF6600",
        "medium": "#FFCC00",
        "low": "#36A64F",
    }

    actor_label = (
        f"AI Agent: {alert.agent_name}" if alert.agent_name
        else f"User: {alert.actor_email or alert.actor_type}"
    )

    payload = {
        "attachments": [
            {
                "color": color_map.get(alert.severity, "#888888"),
                "title": f"🚨 Sentinel Alert — {alert.rule.name}",
                "text": alert.risk_explanation or "Risk threshold exceeded.",
                "fields": [
                    {"title": "Severity", "value": alert.severity.upper(), "short": True},
                    {"title": "Risk Score", "value": str(alert.risk_score or "N/A"), "short": True},
                    {"title": "Actor", "value": actor_label, "short": True},
                    {"title": "Actor Type", "value": alert.actor_type, "short": True},
                    {"title": "Alert ID", "value": str(alert.id)[:8] + "...", "short": True},
                ],
                "footer": "Sentinel Trust Layer",
                "ts": int(alert.created_at.timestamp()),
            }
        ]
    }

    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            str(webhook_url),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                _record_delivery(alert, "slack", "success")
                logger.info("slack_notification_sent", alert_id=alert_id)
            else:
                _record_delivery(alert, "slack", f"http_{resp.status}")
    except Exception as exc:
        _record_delivery(alert, "slack", f"error: {exc}")
        logger.error("slack_notification_failed", alert_id=alert_id, error=str(exc))
        raise self.retry(exc=exc)  # type: ignore[union-attr]


@shared_task(
    name="sentinel.notifications.deliver_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def deliver_email_task(
    self: object,
    alert_id: str,
    config: dict[str, object],
) -> None:
    """Send alert notification via Django email backend."""
    from django.core.mail import send_mail

    from sentinel.risk.models import Alert

    recipients = config.get("to", [])
    if not recipients:
        logger.warning("email_no_recipients", alert_id=alert_id)
        return

    try:
        alert = Alert.objects.select_related("rule").get(id=uuid.UUID(alert_id))
    except Alert.DoesNotExist:
        return

    actor_label = (
        f"AI Agent '{alert.agent_name}'" if alert.agent_name
        else f"User {alert.actor_email or alert.actor_type}"
    )

    subject = f"[Sentinel] {alert.severity.upper()} Alert — {alert.rule.name}"
    body = (
        f"Sentinel has detected a {alert.severity} severity event.\n\n"
        f"Rule: {alert.rule.name}\n"
        f"Actor: {actor_label} (type: {alert.actor_type})\n"
        f"Risk Score: {alert.risk_score or 'N/A'} / 100\n"
        f"Level: {alert.risk_level.upper() if alert.risk_level else 'N/A'}\n\n"
        f"Details:\n{alert.risk_explanation or 'No details available.'}\n\n"
        f"Alert ID: {alert.id}\n"
        f"Time: {alert.created_at.isoformat()}\n\n"
        "Log in to Sentinel to investigate and resolve this alert."
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email="sentinel-alerts@sentinel.io",
            recipient_list=list(recipients),
            fail_silently=False,
        )
        _record_delivery(alert, "email", "success")
        logger.info("email_notification_sent", alert_id=alert_id, recipients=recipients)
    except Exception as exc:
        _record_delivery(alert, "email", f"error: {exc}")
        logger.error("email_notification_failed", alert_id=alert_id, error=str(exc))
        raise self.retry(exc=exc)  # type: ignore[union-attr]


@shared_task(
    name="sentinel.notifications.deliver_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def deliver_webhook_task(
    self: object,
    alert_id: str,
    config: dict[str, object],
) -> None:
    """POST alert JSON to an outbound webhook with HMAC-SHA256 signature."""
    import hashlib
    import hmac as hmac_module
    import urllib.request

    from sentinel.risk.models import Alert

    url = config.get("url")
    secret = config.get("secret", "")

    if not url:
        logger.warning("webhook_no_url", alert_id=alert_id)
        return

    try:
        alert = Alert.objects.select_related("rule").get(id=uuid.UUID(alert_id))
    except Alert.DoesNotExist:
        return

    payload = {
        "alert_id": str(alert.id),
        "rule_name": alert.rule.name,
        "severity": alert.severity,
        "status": alert.status,
        "actor_type": alert.actor_type,
        "actor_email": alert.actor_email,
        "agent_name": alert.agent_name,
        "risk_score": alert.risk_score,
        "risk_level": alert.risk_level,
        "risk_explanation": alert.risk_explanation,
        "created_at": alert.created_at.isoformat(),
    }
    body = json.dumps(payload).encode()

    # HMAC signature so the receiver can verify authenticity
    signature = ""
    if secret:
        signature = hmac_module.new(
            key=str(secret).encode(),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()

    try:
        headers = {
            "Content-Type": "application/json",
            "X-Sentinel-Signature": f"sha256={signature}",
            "X-Sentinel-Alert-ID": str(alert.id),
        }
        req = urllib.request.Request(
            str(url), data=body, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            _record_delivery(alert, "webhook", f"http_{resp.status}")
            if resp.status < 300:
                logger.info("webhook_notification_sent", alert_id=alert_id, url=url)
            else:
                logger.warning("webhook_non_2xx", alert_id=alert_id, status=resp.status)
    except Exception as exc:
        _record_delivery(alert, "webhook", f"error: {exc}")
        logger.error("webhook_notification_failed", alert_id=alert_id, error=str(exc))
        raise self.retry(exc=exc)  # type: ignore[union-attr]


def _record_delivery(alert: object, channel: str, outcome: str) -> None:
    """Append a delivery record to the alert's notifications_sent field."""
    from django.utils import timezone
    from sentinel.risk.models import Alert

    if not isinstance(alert, Alert):
        return

    record = {
        "channel": channel,
        "outcome": outcome,
        "timestamp": timezone.now().isoformat(),
    }
    Alert.objects.filter(id=alert.id).update(
        notifications_sent=alert.notifications_sent + [record]
    )
