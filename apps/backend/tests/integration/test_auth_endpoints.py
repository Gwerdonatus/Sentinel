"""
Integration Tests — Auth Endpoints.

Full HTTP cycle tests for all Phase 2 auth endpoints.
Requires database (pytest-django db fixture).
JWT operations use real simplejwt token generation.
Redis blacklist operations are mocked.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def viewer_user(db: object) -> object:
    return User.objects.create_user(
        email="viewer@sentinel.io",
        password="ViewerPass123!",
        full_name="Test Viewer",
        role="VIEWER",
    )


@pytest.fixture
def admin_user(db: object) -> object:
    return User.objects.create_superuser(
        email="admin@sentinel.io",
        password="AdminPass123!",
        full_name="Test Admin",
    )


@pytest.fixture
def authenticated_client(client: APIClient, viewer_user: object) -> APIClient:
    """Client pre-authenticated via forced auth (bypasses JWT for setup)."""
    client.force_authenticate(user=viewer_user)
    return client


@pytest.mark.django_db
class TestRegisterEndpoint:
    """POST /api/v1/auth/register/"""

    URL = "/api/v1/auth/register/"

    def test_successful_registration_returns_201(self, client: APIClient) -> None:
        response = client.post(self.URL, {
            "email": "newuser@sentinel.io",
            "password": "SecurePassword123!",
            "full_name": "New User",
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_response_includes_user_fields(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "newuser@sentinel.io",
            "password": "SecurePassword123!",
        })
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert data["email"] == "newuser@sentinel.io"
        assert "password" not in data

    def test_default_role_is_viewer(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "newuser@sentinel.io",
            "password": "SecurePassword123!",
        })
        assert response.json()["role"] == "VIEWER"

    def test_duplicate_email_returns_400(self, client: APIClient, viewer_user: object) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "SecurePassword123!",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_weak_password_returns_400(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "newuser@sentinel.io",
            "password": "short",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_email_returns_400(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {"password": "SecurePassword123!"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_email_returns_400(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "not-an-email",
            "password": "SecurePassword123!",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_response_has_request_id_header(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "newuser@sentinel.io",
            "password": "SecurePassword123!",
        })
        assert "X-Request-ID" in response

    def test_unauthenticated_cannot_create_admin_role(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "newadmin@sentinel.io",
            "password": "SecurePassword123!",
            "role": "ADMIN",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestLoginEndpoint:
    """POST /api/v1/auth/login/"""

    URL = "/api/v1/auth/login/"

    def test_valid_credentials_return_200(self, client: APIClient, viewer_user: object) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "ViewerPass123!",
        })
        assert response.status_code == status.HTTP_200_OK

    def test_response_includes_access_and_refresh_tokens(
        self, client: APIClient, viewer_user: object
    ) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "ViewerPass123!",
        })
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["token_type"] == "Bearer"
        assert "expires_in" in data

    def test_response_includes_user_object(
        self, client: APIClient, viewer_user: object
    ) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "ViewerPass123!",
        })
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "viewer@sentinel.io"
        assert "password" not in data["user"]

    def test_wrong_password_returns_401(self, client: APIClient, viewer_user: object) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "WrongPassword!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unknown_email_returns_401(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "email": "ghost@sentinel.io",
            "password": "SomePassword123!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_error_response_does_not_reveal_user_existence(
        self, client: APIClient, db: object
    ) -> None:
        """Security: same error message for wrong email and wrong password."""
        response_no_user = client.post(self.URL, {
            "email": "nonexistent@sentinel.io",
            "password": "WrongPassword!",
        })
        response_wrong_pass = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "WrongPassword!",
        })
        assert response_no_user.json()["error"]["message"] == \
               response_wrong_pass.json()["error"]["message"]

    def test_missing_fields_return_400(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {"email": "viewer@sentinel.io"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_error_response_format_is_consistent(
        self, client: APIClient, viewer_user: object
    ) -> None:
        response = client.post(self.URL, {
            "email": "viewer@sentinel.io",
            "password": "wrong",
        })
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "request_id" in data["error"]


@pytest.mark.django_db
class TestTokenRefreshEndpoint:
    """POST /api/v1/auth/refresh/"""

    URL = "/api/v1/auth/refresh/"
    LOGIN_URL = "/api/v1/auth/login/"

    def _get_refresh_token(self, client: APIClient, viewer_user: object) -> str:
        response = client.post(self.LOGIN_URL, {
            "email": "viewer@sentinel.io",
            "password": "ViewerPass123!",
        })
        return response.json()["refresh"]

    def test_valid_refresh_token_returns_new_pair(
        self, client: APIClient, viewer_user: object
    ) -> None:
        with patch("sentinel.auth_service.services.AuthService._is_blacklisted", return_value=False), \
             patch("sentinel.auth_service.services.AuthService._blacklist_jti"):
            refresh = self._get_refresh_token(client, viewer_user)
            response = client.post(self.URL, {"refresh": refresh})
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "access" in data
            assert "refresh" in data

    def test_blacklisted_token_returns_401(
        self, client: APIClient, viewer_user: object
    ) -> None:
        with patch("sentinel.auth_service.services.AuthService._is_blacklisted", return_value=True):
            refresh = self._get_refresh_token(client, viewer_user)
            response = client.post(self.URL, {"refresh": refresh})
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_token_returns_401(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {"refresh": "not.a.valid.token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_refresh_field_returns_400(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogoutEndpoint:
    """POST /api/v1/auth/logout/"""

    URL = "/api/v1/auth/logout/"

    def test_logout_returns_204(
        self, authenticated_client: APIClient, viewer_user: object
    ) -> None:
        with patch("sentinel.auth_service.services.AuthService._blacklist_jti"):
            response = authenticated_client.post(self.URL, {"refresh": "some.refresh.token"})
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_unauthenticated_logout_returns_401(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {"refresh": "some.refresh.token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_refresh_field_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.post(self.URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMeEndpoint:
    """GET /api/v1/auth/me/"""

    URL = "/api/v1/auth/me/"

    def test_returns_current_user(
        self, authenticated_client: APIClient, viewer_user: object
    ) -> None:
        response = authenticated_client.get(self.URL)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "viewer@sentinel.io"

    def test_response_excludes_password(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.get(self.URL)
        assert "password" not in response.json()

    def test_unauthenticated_returns_401(self, client: APIClient, db: object) -> None:
        response = client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_response_includes_role(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.get(self.URL)
        assert "role" in response.json()
        assert response.json()["role"] == "VIEWER"


@pytest.mark.django_db
class TestPasswordChangeEndpoint:
    """POST /api/v1/auth/me/password/"""

    URL = "/api/v1/auth/me/password/"

    def test_valid_password_change_returns_200(
        self, authenticated_client: APIClient, viewer_user: object
    ) -> None:
        response = authenticated_client.post(self.URL, {
            "current_password": "ViewerPass123!",
            "new_password": "NewSecurePass456!",
        })
        assert response.status_code == status.HTTP_200_OK

    def test_wrong_current_password_returns_422(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.post(self.URL, {
            "current_password": "WrongPassword!",
            "new_password": "NewSecurePass456!",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_same_password_returns_422(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.post(self.URL, {
            "current_password": "ViewerPass123!",
            "new_password": "ViewerPass123!",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_weak_new_password_returns_400(
        self, authenticated_client: APIClient
    ) -> None:
        response = authenticated_client.post(self.URL, {
            "current_password": "ViewerPass123!",
            "new_password": "weak",
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_returns_401(self, client: APIClient, db: object) -> None:
        response = client.post(self.URL, {
            "current_password": "any",
            "new_password": "NewSecurePass456!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
