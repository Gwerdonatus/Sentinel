"""
Integration Tests — API v1 Endpoints.

Tests the full HTTP cycle for Phase 1 API endpoints.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestAPIRootView:
    """GET /api/v1/"""

    def test_returns_200(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        assert response.status_code == 200

    def test_no_authentication_required(self, client: APIClient) -> None:
        """API root must be publicly accessible for SDK discovery."""
        response = client.get("/api/v1/")
        assert response.status_code == 200

    def test_returns_service_name(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert data["service"] == "sentinel"

    def test_returns_api_version(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert data["api_version"] == "v1"

    def test_returns_version_string(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_returns_endpoints_dict(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "endpoints" in data
        assert isinstance(data["endpoints"], dict)

    def test_endpoints_includes_ping(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "ping" in data["endpoints"]

    def test_endpoints_includes_health(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "health" in data["endpoints"]

    def test_returns_features_dict(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "features" in data

    def test_phase_1_features_are_disabled(self, client: APIClient) -> None:
        """Phase 1 only has foundation — all major features are False."""
        response = client.get("/api/v1/")
        data = response.json()
        features = data["features"]
        assert features["authentication"] is False
        assert features["audit_ledger"] is False
        assert features["risk_scoring"] is False
        assert features["alerting"] is False

    def test_returns_timestamp(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert "timestamp" in data

    def test_response_content_type_is_json(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        assert "application/json" in response["Content-Type"]

    def test_response_includes_request_id_header(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        assert "X-Request-ID" in response

    def test_request_id_is_valid_uuid(self, client: APIClient) -> None:
        import uuid
        response = client.get("/api/v1/")
        request_id = response["X-Request-ID"]
        # Raises ValueError if not a valid UUID
        uuid.UUID(request_id)

    def test_propagates_client_request_id(self, client: APIClient) -> None:
        import uuid
        my_request_id = str(uuid.uuid4())
        response = client.get("/api/v1/", HTTP_X_REQUEST_ID=my_request_id)
        assert response["X-Request-ID"] == my_request_id

    def test_status_is_operational(self, client: APIClient) -> None:
        response = client.get("/api/v1/")
        data = response.json()
        assert data["status"] == "operational"


@pytest.mark.django_db
class TestPingView:
    """GET /api/v1/ping/"""

    def test_returns_200(self, client: APIClient) -> None:
        response = client.get("/api/v1/ping/")
        assert response.status_code == 200

    def test_no_authentication_required(self, client: APIClient) -> None:
        response = client.get("/api/v1/ping/")
        assert response.status_code == 200

    def test_returns_pong_true(self, client: APIClient) -> None:
        response = client.get("/api/v1/ping/")
        data = response.json()
        assert data["pong"] is True

    def test_returns_timestamp(self, client: APIClient) -> None:
        response = client.get("/api/v1/ping/")
        data = response.json()
        assert "timestamp" in data

    def test_returns_request_id_in_body(self, client: APIClient) -> None:
        import uuid
        my_id = str(uuid.uuid4())
        response = client.get("/api/v1/ping/", HTTP_X_REQUEST_ID=my_id)
        data = response.json()
        assert data["request_id"] == my_id

    def test_response_content_type_is_json(self, client: APIClient) -> None:
        response = client.get("/api/v1/ping/")
        assert "application/json" in response["Content-Type"]

    def test_post_method_not_allowed(self, client: APIClient) -> None:
        response = client.post("/api/v1/ping/", data={})
        assert response.status_code == 405

    def test_delete_method_not_allowed(self, client: APIClient) -> None:
        response = client.delete("/api/v1/ping/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestNotFoundBehavior:
    """Tests for non-existent endpoints."""

    def test_unknown_api_path_returns_404(self, client: APIClient) -> None:
        response = client.get("/api/v1/nonexistent-endpoint/")
        assert response.status_code == 404

    def test_404_response_is_json(self, client: APIClient) -> None:
        response = client.get("/api/v1/nonexistent-endpoint/")
        # Should be JSON, not HTML
        assert "application/json" in response["Content-Type"]
