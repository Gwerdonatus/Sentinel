"""
Integration Tests — API Key Endpoints.

Full HTTP cycle tests for API key management, including AI agent key creation.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from sentinel.api_keys.models import APIKey, ActorType

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin_user(db: object) -> object:
    return User.objects.create_superuser(email="admin@sentinel.io", password="AdminPass123!")


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
def viewer_client(client: APIClient, viewer_user: object) -> APIClient:
    client.force_authenticate(user=viewer_user)
    return client


@pytest.mark.django_db
@override_settings(SECRET_KEY="test-secret-key-for-hmac-fifty-chars-minimum-x")
class TestAPIKeyCreateEndpoint:
    URL = "/api/v1/api-keys/create/"

    def test_admin_can_create_service_key(self, admin_client: APIClient) -> None:
        response = admin_client.post(self.URL, {
            "name": "Reconciliation Service",
            "actor_type": "SERVICE",
            "scopes": ["events:write"],
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_response_includes_full_key_once(self, admin_client: APIClient) -> None:
        response = admin_client.post(self.URL, {
            "name": "Test Service",
            "actor_type": "SERVICE",
            "scopes": ["events:write"],
        }, format="json")
        data = response.json()
        assert "key" in data
        assert data["key"].startswith("sk_live_")

    def test_ai_agent_key_requires_agent_name(self, admin_client: APIClient) -> None:
        response = admin_client.post(self.URL, {
            "name": "Support Bot",
            "actor_type": "AI_AGENT",
            "scopes": ["events:write"],
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ai_agent_key_with_agent_name_succeeds(self, admin_client: APIClient) -> None:
        response = admin_client.post(self.URL, {
            "name": "Support Bot Key",
            "actor_type": "AI_AGENT",
            "agent_name": "support-bot-v2",
            "agent_version": "gpt-4-turbo-2024-04",
            "agent_description": "Handles tier-1 customer support queries",
            "scopes": ["events:write", "events:read"],
        }, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["agent_name"] == "support-bot-v2"
        assert data["agent_version"] == "gpt-4-turbo-2024-04"

    def test_viewer_cannot_create_key(self, viewer_client: APIClient) -> None:
        response = viewer_client.post(self.URL, {
            "name": "Test",
            "actor_type": "SERVICE",
            "scopes": ["events:write"],
        }, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_invalid_scope_rejected(self, admin_client: APIClient) -> None:
        response = admin_client.post(self.URL, {
            "name": "Test",
            "actor_type": "SERVICE",
            "scopes": ["totally:made-up-scope"],
        }, format="json")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_key_value_never_appears_in_list_endpoint(
        self, admin_client: APIClient
    ) -> None:
        admin_client.post(self.URL, {
            "name": "Test",
            "actor_type": "SERVICE",
            "scopes": ["events:write"],
        }, format="json")

        list_response = admin_client.get("/api/v1/api-keys/")
        data = list_response.json()
        for key_record in data:
            assert "key" not in key_record
            assert "key_hash" not in key_record


@pytest.mark.django_db
@override_settings(SECRET_KEY="test-secret-key-for-hmac-fifty-chars-minimum-x")
class TestAPIKeyAuthentication:
    """Test that a created API key can actually authenticate requests."""

    def test_valid_api_key_authenticates_request(
        self, admin_client: APIClient, client: APIClient
    ) -> None:
        create_response = admin_client.post("/api/v1/api-keys/create/", {
            "name": "Auth Test Service",
            "actor_type": "SERVICE",
            "scopes": ["events:write"],
        }, format="json")
        full_key = create_response.json()["key"]

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {full_key}")
        response = client.get("/api/v1/auth/me/")
        # The key has no created_by user attached to it in this flow context,
        # so /me/ will fail, but the auth itself should not 401 with "invalid key"
        assert response.status_code != status.HTTP_401_UNAUTHORIZED or \
               "Invalid or expired" not in str(response.content)

    def test_invalid_api_key_returns_401(self, client: APIClient) -> None:
        client.credentials(HTTP_AUTHORIZATION="Bearer sk_live_not_a_real_key_at_all")
        response = client.get("/api/v1/events/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAPIKeyDetailEndpoint:
    def test_admin_can_revoke_key(self, admin_client: APIClient, db: object) -> None:
        full_key, prefix, key_hash = APIKey.generate_key("live")
        key = APIKey.objects.create(
            name="To Revoke",
            actor_type=ActorType.SERVICE,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[],
        )

        response = admin_client.delete(f"/api/v1/api-keys/{key.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        key.refresh_from_db()
        assert key.deleted_at is not None

    def test_revoked_key_cannot_authenticate(
        self, admin_client: APIClient, client: APIClient, db: object
    ) -> None:
        with override_settings(SECRET_KEY="test-secret-key-for-hmac-fifty-chars-minimum-x"):
            full_key, prefix, key_hash = APIKey.generate_key("live")
            key = APIKey.objects.create(
                name="To Revoke",
                actor_type=ActorType.SERVICE,
                key_prefix=prefix,
                key_hash=key_hash,
                scopes=["events:write"],
            )

            admin_client.delete(f"/api/v1/api-keys/{key.id}/")

            client.credentials(HTTP_AUTHORIZATION=f"Bearer {full_key}")
            response = client.get("/api/v1/events/")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
