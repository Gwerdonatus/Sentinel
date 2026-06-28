"""
Integration Tests — Audit Event Endpoints.

Full HTTP cycle tests for the audit ledger API.
Tests immutability enforcement, access control, and signature verification.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from sentinel.audit.models import AuditEvent

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def auditor_user(db: object) -> object:
    return User.objects.create_user(
        email="auditor@sentinel.io",
        password="AuditorPass123!",
        role="AUDITOR",
    )


@pytest.fixture
def analyst_user(db: object) -> object:
    return User.objects.create_user(
        email="analyst@sentinel.io",
        password="AnalystPass123!",
        role="ANALYST",
    )


@pytest.fixture
def viewer_user(db: object) -> object:
    return User.objects.create_user(
        email="viewer@sentinel.io",
        password="ViewerPass123!",
        role="VIEWER",
    )


@pytest.fixture
def auditor_client(client: APIClient, auditor_user: object) -> APIClient:
    client.force_authenticate(user=auditor_user)
    return client


@pytest.fixture
def analyst_client(client: APIClient, analyst_user: object) -> APIClient:
    client.force_authenticate(user=analyst_user)
    return client


@pytest.fixture
def viewer_client(client: APIClient, viewer_user: object) -> APIClient:
    client.force_authenticate(user=viewer_user)
    return client


@pytest.fixture
def sample_event(db: object) -> AuditEvent:
    """A real AuditEvent in the database for read tests."""
    return AuditEvent.objects.create(
        event_type="USER_LOGIN",
        actor_id=uuid.uuid4(),
        actor_email="someuser@sentinel.io",
        actor_role="VIEWER",
        actor_ip="1.2.3.4",
        resource_type="user",
        resource_id="some-user-id",
        metadata={"ip_address": "1.2.3.4"},
        request_id="req-abc-123",
        signature="a" * 64,
    )


@pytest.mark.django_db
class TestAuditEventListEndpoint:
    """GET /api/v1/events/"""

    URL = "/api/v1/events/"

    def test_auditor_can_list_events(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = auditor_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_response_is_paginated(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = auditor_client.get(self.URL)
        data = response.json()
        assert "pagination" in data
        assert "results" in data

    def test_viewer_cannot_list_events(
        self, viewer_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = viewer_client.get(self.URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_list_events(
        self, client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_filter_by_event_type(
        self, auditor_client: APIClient, sample_event: AuditEvent, db: object
    ) -> None:
        # Create a second event of different type
        AuditEvent.objects.create(
            event_type="USER_LOGOUT",
            actor_email="other@sentinel.io",
            metadata={},
            signature="b" * 64,
        )
        response = auditor_client.get(self.URL, {"event_type": "USER_LOGIN"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert all(e["event_type"] == "USER_LOGIN" for e in results)

    def test_filter_by_actor_id(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = auditor_client.get(
            self.URL, {"actor_id": str(sample_event.actor_id)}
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["actor_email"] == "someuser@sentinel.io"

    def test_invalid_event_type_filter_returns_400(
        self, auditor_client: APIClient
    ) -> None:
        response = auditor_client.get(self.URL, {"event_type": "INVALID_TYPE"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_from_dt_after_to_dt_returns_400(
        self, auditor_client: APIClient
    ) -> None:
        response = auditor_client.get(self.URL, {
            "from_dt": "2025-12-31T00:00:00Z",
            "to_dt": "2025-01-01T00:00:00Z",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAuditEventDetailEndpoint:
    """GET /api/v1/events/{id}/"""

    def test_auditor_can_retrieve_event(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = auditor_client.get(f"/api/v1/events/{sample_event.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_response_includes_all_fields(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = auditor_client.get(f"/api/v1/events/{sample_event.id}/")
        data = response.json()
        expected_fields = [
            "id", "event_type", "actor_id", "actor_email", "actor_role",
            "actor_ip", "resource_type", "resource_id", "metadata",
            "request_id", "signature", "created_at",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    def test_viewer_cannot_retrieve_event(
        self, viewer_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = viewer_client.get(f"/api/v1/events/{sample_event.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_event_returns_404(
        self, auditor_client: APIClient, db: object
    ) -> None:
        response = auditor_client.get(f"/api/v1/events/{uuid.uuid4()}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_uuid_returns_422(
        self, auditor_client: APIClient, db: object
    ) -> None:
        response = auditor_client.get("/api/v1/events/not-a-uuid/")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_put_method_not_allowed(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        """Audit events are immutable — no updates allowed."""
        response = auditor_client.put(
            f"/api/v1/events/{sample_event.id}/", {"event_type": "USER_LOGOUT"}
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_delete_method_not_allowed(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        """Audit events are immutable — no deletions allowed."""
        response = auditor_client.delete(f"/api/v1/events/{sample_event.id}/")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
class TestAuditEventIngestEndpoint:
    """POST /api/v1/events/ingest/"""

    URL = "/api/v1/events/ingest/"

    def test_analyst_can_ingest_event(
        self, analyst_client: APIClient
    ) -> None:
        response = analyst_client.post(self.URL, {
            "event_type": "TRANSFER_INITIATED",
            "actor_email": "user@example.com",
            "resource_type": "transfer",
            "resource_id": "txn-001",
            "metadata": {"amount": 5000, "currency": "NGN"},
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_ingest_response_includes_id_and_signature(
        self, analyst_client: APIClient
    ) -> None:
        response = analyst_client.post(self.URL, {
            "event_type": "USER_LOGIN",
            "actor_email": "user@example.com",
            "metadata": {},
        })
        data = response.json()
        assert "id" in data
        assert "signature" in data
        assert len(data["signature"]) == 64

    def test_viewer_cannot_ingest_event(
        self, viewer_client: APIClient
    ) -> None:
        response = viewer_client.post(self.URL, {
            "event_type": "USER_LOGIN",
            "metadata": {},
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unknown_event_type_returns_422(
        self, analyst_client: APIClient
    ) -> None:
        response = analyst_client.post(self.URL, {
            "event_type": "COMPLETELY_MADE_UP_EVENT",
            "metadata": {},
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_ingested_event_is_persisted(
        self, analyst_client: APIClient, db: object
    ) -> None:
        initial_count = AuditEvent.objects.count()
        analyst_client.post(self.URL, {
            "event_type": "ADMIN_ACTION",
            "metadata": {"action": "config_change"},
        })
        assert AuditEvent.objects.count() == initial_count + 1

    def test_unauthenticated_cannot_ingest(
        self, client: APIClient, db: object
    ) -> None:
        response = client.post(self.URL, {
            "event_type": "USER_LOGIN",
            "metadata": {},
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAuditEventVerifyEndpoint:
    """GET /api/v1/events/{id}/verify/"""

    def test_valid_signature_returns_valid_true(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        with patch(
            "sentinel.audit.services.AuditEventService.verify_signature",
            return_value=True,
        ):
            response = auditor_client.get(
                f"/api/v1/events/{sample_event.id}/verify/"
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is True
        assert "unmodified" in data["message"]

    def test_invalid_signature_returns_valid_false(
        self, auditor_client: APIClient, sample_event: AuditEvent
    ) -> None:
        with patch(
            "sentinel.audit.services.AuditEventService.verify_signature",
            return_value=False,
        ):
            response = auditor_client.get(
                f"/api/v1/events/{sample_event.id}/verify/"
            )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["valid"] is False
        assert "INVALID" in data["message"]

    def test_viewer_cannot_verify(
        self, viewer_client: APIClient, sample_event: AuditEvent
    ) -> None:
        response = viewer_client.get(
            f"/api/v1/events/{sample_event.id}/verify/"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAuditImmutabilityAtRepository:
    """Verify the repository raises on update/delete — the first immutability layer."""

    def test_repository_update_raises(self) -> None:
        from sentinel.audit.repositories import AuditEventRepository
        repo = AuditEventRepository()
        with pytest.raises(NotImplementedError, match="immutable"):
            repo.update()

    def test_repository_delete_raises(self) -> None:
        from sentinel.audit.repositories import AuditEventRepository
        repo = AuditEventRepository()
        with pytest.raises(NotImplementedError, match="immutable"):
            repo.delete()
