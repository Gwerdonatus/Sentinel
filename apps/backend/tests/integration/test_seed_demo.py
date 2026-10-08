from __future__ import annotations

from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from config.celery import app
from sentinel.api_keys.models import APIKey
from sentinel.audit.models import AuditEvent, AuditOutbox
from sentinel.audit.services import AuditEventService
from sentinel.kafka.consumer import SentinelKafkaConsumer
from sentinel.risk.models import Alert


@pytest.mark.django_db
def test_demo_reseed_preserves_identity_events_and_kafka_alerts() -> None:
    with patch("sentinel.api_keys.services.record_audit_event_task.delay"):
        call_command("seed_demo", stdout=StringIO())

    key = APIKey.objects.get(name="Demo Reconciliation Agent")
    events = AuditEvent.objects.filter(metadata__demo_data=True)
    event_ids = set(events.values_list("id", flat=True))
    assert len(event_ids) == 9
    assert set(events.values_list("actor_id", flat=True)) == {key.id}
    assert AuditOutbox.objects.filter(audit_event_id__in=event_ids).count() == 9
    assert not Alert.objects.exists()
    assert all(AuditEventService().verify_signature(event) for event in events)

    suspicious = events.get(request_id="demo-suspicious-transfer")
    consumer = SentinelKafkaConsumer(topics=["sentinel.default.audit.events"], group_id="test")
    with (
        patch("sentinel.kafka.producer.publish_risk_score"),
        patch("sentinel.notifications.tasks.dispatch_alert_notifications_task.delay"),
        patch.object(consumer, "_consumer") as broker,
    ):
        message = Mock()
        message.value.return_value = (
            '{"schema_version":"1.0","id":"' + str(suspicious.id) + '"}'
        ).encode()
        consumer._process_message(message)
        broker.commit.assert_called_once_with(message)

    suspicious.refresh_from_db()
    assert suspicious.risk_score == 60
    alert_ids = set(Alert.objects.filter(audit_event_id=suspicious.id).values_list("id", flat=True))
    assert len(alert_ids) == 2

    with patch("sentinel.api_keys.services.record_audit_event_task.delay") as audit_task:
        call_command("seed_demo", stdout=StringIO())
        audit_task.assert_not_called()

    assert APIKey.objects.filter(name="Demo Reconciliation Agent").count() == 1
    assert set(events.values_list("id", flat=True)) == event_ids
    assert (
        set(Alert.objects.filter(audit_event_id=suspicious.id).values_list("id", flat=True))
        == alert_ids
    )
    key.refresh_from_db()
    assert key.rotation_grace_until is None
    admin = get_user_model().objects.get(email="demo.admin@sentinel.local")
    assert admin.check_password("SentinelDemo123!")


def test_default_tasks_use_the_queue_consumed_by_compose_worker() -> None:
    assert app.conf.task_default_queue == "default"
