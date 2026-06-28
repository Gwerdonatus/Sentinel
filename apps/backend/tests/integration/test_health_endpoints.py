"""
Integration Tests — Health Endpoints.

Tests the full HTTP request/response cycle for all health endpoints.
Requires database and cache (uses pytest-django's db fixture).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.django_db
class TestLivenessEndpoint:
    """GET /health/live/"""

    def test_returns_200(self, client: Client) -> None:
        response = client.get("/health/live/")
        assert response.status_code == 200

    def test_returns_ok_status(self, client: Client) -> None:
        response = client.get("/health/live/")
        data = response.json()
        assert data["status"] == "ok"

    def test_returns_service_name(self, client: Client) -> None:
        response = client.get("/health/live/")
        data = response.json()
        assert data["service"] == "sentinel"

    def test_no_authentication_required(self, client: Client) -> None:
        """Liveness probe must not require auth — load balancers don't authenticate."""
        response = client.get("/health/live/")
        assert response.status_code == 200

    def test_responds_even_without_database(self, client: Client) -> None:
        """
        Liveness is about whether the process is running,
        not whether dependencies are available.
        """
        with patch("django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
                   side_effect=Exception("DB down")):
            response = client.get("/health/live/")
            assert response.status_code == 200


@pytest.mark.django_db
class TestReadinessEndpoint:
    """GET /health/ready/"""

    def test_returns_200_when_all_healthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)

            response = client.get("/health/ready/")
            assert response.status_code == 200

    def test_returns_503_when_database_unhealthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult(
                "database", CheckStatus.ERROR, 5000.0, "Connection refused"
            )
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)

            response = client.get("/health/ready/")
            assert response.status_code == 503

    def test_returns_503_when_redis_unhealthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult(
                "redis", CheckStatus.ERROR, 5000.0, "Connection refused"
            )

            response = client.get("/health/ready/")
            assert response.status_code == 503

    def test_response_includes_checks_dict(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)

            response = client.get("/health/ready/")
            data = response.json()
            assert "checks" in data
            assert "database" in data["checks"]
            assert "redis" in data["checks"]

    def test_ready_status_string_when_healthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)

            response = client.get("/health/ready/")
            data = response.json()
            assert data["status"] == "ready"

    def test_not_ready_status_string_when_unhealthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult(
                "database", CheckStatus.ERROR, 100.0, "timeout"
            )
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)

            response = client.get("/health/ready/")
            data = response.json()
            assert data["status"] == "not_ready"


@pytest.mark.django_db
class TestHealthSummaryEndpoint:
    """GET /health/"""

    def test_returns_200_when_all_healthy(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult(
                "celery", CheckStatus.OK, 50.0, metadata={"active_workers": 2}
            )

            response = client.get("/health/")
            assert response.status_code == 200

    def test_response_includes_version(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult("celery", CheckStatus.OK, 50.0)

            response = client.get("/health/")
            data = response.json()
            assert "version" in data
            assert "service" in data
            assert data["service"] == "sentinel"

    def test_response_includes_total_ms(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult("celery", CheckStatus.OK, 50.0)

            response = client.get("/health/")
            data = response.json()
            assert "total_ms" in data
            assert isinstance(data["total_ms"], float)

    def test_returns_503_when_any_check_fails(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult(
                "database", CheckStatus.ERROR, 5000.0, "Timeout"
            )
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult("celery", CheckStatus.OK, 50.0)

            response = client.get("/health/")
            assert response.status_code == 503

    def test_healthy_status_string(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult("database", CheckStatus.OK, 5.0)
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult("celery", CheckStatus.OK, 50.0)

            response = client.get("/health/")
            data = response.json()
            assert data["status"] == "healthy"

    def test_degraded_status_string_on_failure(self, client: Client) -> None:
        with patch("sentinel.core.health.checks.check_database") as mock_db, \
             patch("sentinel.core.health.checks.check_redis") as mock_redis, \
             patch("sentinel.core.health.checks.check_celery") as mock_celery:
            from sentinel.core.health.checks import CheckResult, CheckStatus
            mock_db.return_value = CheckResult(
                "database", CheckStatus.ERROR, 5000.0, "timeout"
            )
            mock_redis.return_value = CheckResult("redis", CheckStatus.OK, 2.0)
            mock_celery.return_value = CheckResult("celery", CheckStatus.OK, 50.0)

            response = client.get("/health/")
            data = response.json()
            assert data["status"] == "degraded"
