"""
Sentinel Test Configuration.

Shared fixtures available to all test modules.
Follows pytest's convention — conftest.py at the project root
makes these fixtures available without explicit imports.

Fixture hierarchy:
    db        — pytest-django managed: wraps each test in a transaction
    client    — DRF APIClient (unauthenticated)
    api_url   — URL builder helper
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient


# =============================================================================
# API Client Fixtures
# =============================================================================

@pytest.fixture
def api_client() -> APIClient:
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client: APIClient, db: object) -> APIClient:
    """
    DRF API client pre-authenticated as a test user.
    Phase 2+: Will use JWT token authentication.
    Phase 1: Uses session authentication.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        email="test@sentinel.io",
        password="TestPassword123!",
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_api_client(api_client: APIClient, db: object) -> APIClient:
    """DRF API client authenticated as a superuser."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@sentinel.io",
        password="AdminPassword123!",
    )
    api_client.force_authenticate(user=admin)
    return api_client


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def db_no_migrations(db: object) -> object:
    """
    Alias for db fixture.
    Explicitly communicates that a test needs the DB but doesn't
    create any migrations itself.
    """
    return db


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_cache() -> Generator[object, None, None]:
    """Mock Django cache for tests that should not hit Redis."""
    with patch("django.core.cache.cache") as mock:
        yield mock


@pytest.fixture
def mock_celery_task() -> Generator[object, None, None]:
    """Mock Celery task dispatch to prevent actual task execution in unit tests."""
    with patch("celery.app.task.Task.delay") as mock:
        yield mock


# =============================================================================
# URL Helpers
# =============================================================================

@pytest.fixture
def api_v1_url() -> str:
    """Base URL for API v1 endpoints."""
    return "/api/v1"


# =============================================================================
# Marker Configuration
# =============================================================================

def pytest_configure(config: object) -> None:
    """Register custom pytest markers to prevent warnings."""
    import _pytest.config

    cfg: _pytest.config.Config = config  # type: ignore[assignment]
    cfg.addinivalue_line("markers", "unit: Unit tests — no database, no network")
    cfg.addinivalue_line("markers", "integration: Integration tests — requires database")
    cfg.addinivalue_line("markers", "slow: Tests that take more than 1 second")
