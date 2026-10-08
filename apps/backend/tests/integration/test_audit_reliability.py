from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from sentinel.api_keys.models import ActorType as APIKeyActorType
from sentinel.api_keys.services import APIKeyService
from sentinel.audit.models import ActorType, AuditOutbox
from sentinel.audit.services import AuditEventService
from sentinel.audit.tasks import publish_pending_audit_events_task

User = get_user_model()


@pytest.mark.django_db
def test_recorded_event_round_trips_signature_and_outbox() -> None:
    service = AuditEventService()
    created_at_before = timezone.now()

    event = service.record(
        event_type="TRANSFER_INITIATED",
        actor_id=str(uuid.uuid4()),
        actor_type=ActorType.AI_AGENT,
        actor_email="",
        actor_role="API_KEY",
        actor_ip="127.0.0.1",
        agent_name="reconciliation-agent",
        resource_type="transfer",
        resource_id="txn-001",
        metadata={"amount": "125.00", "currency": "USD"},
        request_id="req-signature-roundtrip",
    )

    event.refresh_from_db()
    assert event.created_at >= created_at_before
    assert event.signature_version == 2
    assert service.verify_signature(event) is True
    assert AuditOutbox.objects.filter(audit_event=event, published_at__isnull=True).exists()

    type(event).objects.filter(id=event.id).update(resource_id="tampered")
    event.refresh_from_db()
    assert service.verify_signature(event) is False


@pytest.mark.django_db
def test_api_key_identity_overrides_spoofed_actor_fields() -> None:
    owner = User.objects.create_user(
        email="analyst-owner@sentinel.io",
        password="StrongPass123!",
        role="ANALYST",
    )
    api_key, full_key = APIKeyService().create(
        name="Demo Reconciliation Agent",
        actor_type=APIKeyActorType.AI_AGENT,
        scopes=["events:write"],
        created_by=owner,
        agent_name="reconciliation-agent",
        agent_version="v1.0",
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {full_key}")

    response = client.post(
        "/api/v1/events/ingest/",
        {
            "event_type": "TRANSFER_INITIATED",
            "actor_id": str(uuid.uuid4()),
            "actor_email": "spoofed@example.com",
            "actor_role": "ADMIN",
            "actor_ip": "8.8.8.8",
            "resource_type": "transfer",
            "resource_id": "txn-002",
            "metadata": {"source": "demo"},
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["actor_id"] == str(api_key.id)
    assert body["actor_type"] == ActorType.AI_AGENT
    assert body["actor_email"] == ""
    assert body["actor_role"] == "API_KEY"
    assert body["actor_ip"] == "127.0.0.1"
    assert body["agent_name"] == "reconciliation-agent"


@pytest.mark.django_db
def test_api_key_without_write_scope_cannot_ingest() -> None:
    owner = User.objects.create_user(
        email="readonly-owner@sentinel.io",
        password="StrongPass123!",
        role="ANALYST",
    )
    _, full_key = APIKeyService().create(
        name="Read-only integration",
        actor_type=APIKeyActorType.SERVICE,
        scopes=["events:read"],
        created_by=owner,
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {full_key}")

    response = client.post(
        "/api/v1/events/ingest/",
        {"event_type": "USER_LOGIN", "metadata": {}},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_outbox_failure_is_retried_then_marked_published() -> None:
    event = AuditEventService().record(event_type="USER_LOGIN", metadata={})

    with patch(
        "sentinel.kafka.producer.publish_audit_event",
        side_effect=RuntimeError("broker unavailable"),
    ):
        result = publish_pending_audit_events_task.run(batch_size=100)

    entry = AuditOutbox.objects.get(audit_event=event)
    assert result == {"published": 0, "failed": 1}
    assert entry.attempts == 1
    assert entry.published_at is None
    assert "broker unavailable" in entry.last_error

    entry.next_attempt_at = timezone.now()
    entry.save(update_fields=["next_attempt_at"])
    with patch("sentinel.kafka.producer.publish_audit_event") as publish:
        result = publish_pending_audit_events_task.run(batch_size=100)

    entry.refresh_from_db()
    assert result == {"published": 1, "failed": 0}
    assert entry.published_at is not None
    publish.assert_called_once_with(event)
