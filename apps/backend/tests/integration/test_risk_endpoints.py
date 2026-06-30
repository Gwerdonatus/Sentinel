"""
Integration Tests — Risk and Alerts Endpoints.

Full HTTP cycle tests for alert management and risk summary APIs.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from sentinel.audit.models import AuditEvent
from sentinel.risk.models import Alert, AlertRule, AlertSeverity, AlertStatus

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin_user(db: object) -> object:
    return User.objects.create_superuser(email="admin@sentinel.io", password="AdminPass123!")


@pytest.fixture
def analyst_user(db: object) -> object:
    return User.objects.create_user(
        email="analyst@sentinel.io", password="AnalystPass123!", role="ANALYST"
    )


@pytest.fixture
def viewer_user(db: object) -> object:
    return User.objects.create_user(
        email="viewer@sentinel.io", password="ViewerPass123!", role="VIEWER"
    )


@pytest.fixture
def admin_client(client: APIClient, admin_user: object) -> APIClient:
    client.force_authenticate(user=admin_user)
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
def sample_rule(db: object) -> AlertRule:
    return AlertRule.objects.create(
        name="Test Rule",
        condition={"field": "risk_score", "operator": "gte", "value": 75},
        severity=AlertSeverity.CRITICAL,
        notification_channels=[],
    )


@pytest.fixture
def sample_alert(db: object, sample_rule: AlertRule) -> Alert:
    return Alert.objects.create(
        rule=sample_rule,
        audit_event_id=uuid.uuid4(),
        severity=AlertSeverity.CRITICAL,
        actor_type="AI_AGENT",
        agent_name="support-bot",
        risk_score=85,
        risk_level="critical",
        risk_explanation="Test alert",
    )


@pytest.mark.django_db
class TestAlertListEndpoint:
    URL = "/api/v1/alerts/"

    def test_analyst_can_list_alerts(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_viewer_cannot_list_alerts(self, viewer_client: APIClient, sample_alert: Alert) -> None:
        response = viewer_client.get(self.URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_filter_by_severity(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.get(self.URL, {"severity": "critical"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert all(a["severity"] == "critical" for a in results)

    def test_filter_by_actor_type(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.get(self.URL, {"actor_type": "AI_AGENT"})
        results = response.json()["results"]
        assert all(a["actor_type"] == "AI_AGENT" for a in results)

    def test_filter_by_agent_name(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.get(self.URL, {"agent_name": "support-bot"})
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["agent_name"] == "support-bot"


@pytest.mark.django_db
class TestAlertAcknowledgeEndpoint:
    def test_acknowledge_open_alert_succeeds(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        response = analyst_client.post(f"/api/v1/alerts/{sample_alert.id}/acknowledge/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "acknowledged"

    def test_acknowledge_already_acknowledged_fails(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        sample_alert.status = AlertStatus.ACKNOWLEDGED
        sample_alert.save()
        response = analyst_client.post(f"/api/v1/alerts/{sample_alert.id}/acknowledge/")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_acknowledge_sets_acknowledged_by(
        self, analyst_client: APIClient, sample_alert: Alert, analyst_user: object
    ) -> None:
        response = analyst_client.post(f"/api/v1/alerts/{sample_alert.id}/acknowledge/")
        sample_alert.refresh_from_db()
        assert sample_alert.acknowledged_by == analyst_user

    def test_nonexistent_alert_returns_404(self, analyst_client: APIClient) -> None:
        response = analyst_client.post(f"/api/v1/alerts/{uuid.uuid4()}/acknowledge/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAlertResolveEndpoint:
    def test_resolve_alert_succeeds(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.post(
            f"/api/v1/alerts/{sample_alert.id}/resolve/",
            {"note": "False positive — known AI agent batch job."},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "resolved"
        assert response.json()["resolution_note"] == "False positive — known AI agent batch job."

    def test_resolve_already_resolved_fails(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        sample_alert.status = AlertStatus.RESOLVED
        sample_alert.save()
        response = analyst_client.post(f"/api/v1/alerts/{sample_alert.id}/resolve/", {})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_resolve_without_note_succeeds(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        response = analyst_client.post(f"/api/v1/alerts/{sample_alert.id}/resolve/", {})
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestAlertRuleEndpoints:
    URL = "/api/v1/alerts/rules/"

    def test_analyst_can_list_rules(self, analyst_client: APIClient, sample_rule: AlertRule) -> None:
        response = analyst_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_analyst_can_create_rule(self, analyst_client: APIClient) -> None:
        response = analyst_client.post(self.URL, {
            "name": "AI velocity check",
            "condition": {"field": "risk_score", "operator": "gte", "value": 60},
            "severity": "high",
            "notification_channels": ["slack"],
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_viewer_cannot_create_rule(self, viewer_client: APIClient) -> None:
        response = viewer_client.post(self.URL, {
            "name": "Test",
            "condition": {"field": "risk_score", "operator": "gte", "value": 50},
        }, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_notification_channel_rejected(self, analyst_client: APIClient) -> None:
        response = analyst_client.post(self.URL, {
            "name": "Bad channel rule",
            "condition": {"field": "risk_score", "operator": "gte", "value": 50},
            "notification_channels": ["carrier_pigeon"],
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_admin_can_deactivate_rule(
        self, admin_client: APIClient, sample_rule: AlertRule
    ) -> None:
        response = admin_client.delete(f"/api/v1/alerts/rules/{sample_rule.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        sample_rule.refresh_from_db()
        assert sample_rule.is_active is False

    def test_builtin_rule_cannot_be_deleted(self, admin_client: APIClient, db: object) -> None:
        builtin = AlertRule.objects.create(
            name="Builtin Test Rule",
            condition={"field": "risk_score", "operator": "gte", "value": 75},
            is_builtin=True,
        )
        response = admin_client.delete(f"/api/v1/alerts/rules/{builtin.id}/")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.django_db
class TestRiskSummaryEndpoint:
    URL = "/api/v1/risk/summary/"

    def test_analyst_can_view_summary(self, analyst_client: APIClient, sample_alert: Alert) -> None:
        response = analyst_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK

    def test_summary_includes_open_alerts_breakdown(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        response = analyst_client.get(self.URL)
        data = response.json()
        assert "open_alerts" in data
        assert "critical" in data["open_alerts"]

    def test_summary_includes_last_24h_stats(
        self, analyst_client: APIClient, sample_alert: Alert
    ) -> None:
        response = analyst_client.get(self.URL)
        data = response.json()
        assert "last_24h" in data
        assert "ai_agent_events" in data["last_24h"]

    def test_viewer_cannot_view_summary(self, viewer_client: APIClient) -> None:
        response = viewer_client.get(self.URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN
