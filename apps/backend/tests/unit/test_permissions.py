"""
Unit Tests — RBAC Permission Classes.

Tests role-based access control logic in isolation.
No DB or HTTP required — mocks request.user directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sentinel.auth_service.models import Role
from sentinel.auth_service.permissions import (
    IsAdmin,
    IsAnalystOrAbove,
    IsAuditorOrAbove,
    ReadOnly,
)


def make_request(role: str, authenticated: bool = True) -> MagicMock:
    """Build a mock DRF request with a user of the given role."""
    request = MagicMock()
    request.user.is_authenticated = authenticated
    request.user.role = role
    return request


def make_anon_request() -> MagicMock:
    request = MagicMock()
    request.user.is_authenticated = False
    request.user = None
    return request


class TestIsAdmin:
    def test_admin_has_permission(self) -> None:
        perm = IsAdmin()
        assert perm.has_permission(make_request(Role.ADMIN), MagicMock()) is True

    @pytest.mark.parametrize("role", [Role.AUDITOR, Role.ANALYST, Role.VIEWER])
    def test_non_admin_denied(self, role: str) -> None:
        perm = IsAdmin()
        assert perm.has_permission(make_request(role), MagicMock()) is False

    def test_unauthenticated_denied(self) -> None:
        perm = IsAdmin()
        req = make_request(Role.ADMIN, authenticated=False)
        assert perm.has_permission(req, MagicMock()) is False


class TestIsAuditorOrAbove:
    @pytest.mark.parametrize("role", [Role.ADMIN, Role.AUDITOR])
    def test_admin_and_auditor_have_permission(self, role: str) -> None:
        perm = IsAuditorOrAbove()
        assert perm.has_permission(make_request(role), MagicMock()) is True

    @pytest.mark.parametrize("role", [Role.ANALYST, Role.VIEWER])
    def test_analyst_and_viewer_denied(self, role: str) -> None:
        perm = IsAuditorOrAbove()
        assert perm.has_permission(make_request(role), MagicMock()) is False

    def test_unauthenticated_denied(self) -> None:
        perm = IsAuditorOrAbove()
        req = make_request(Role.AUDITOR, authenticated=False)
        assert perm.has_permission(req, MagicMock()) is False


class TestIsAnalystOrAbove:
    @pytest.mark.parametrize("role", [Role.ADMIN, Role.AUDITOR, Role.ANALYST])
    def test_admin_auditor_analyst_have_permission(self, role: str) -> None:
        perm = IsAnalystOrAbove()
        assert perm.has_permission(make_request(role), MagicMock()) is True

    def test_viewer_denied(self) -> None:
        perm = IsAnalystOrAbove()
        assert perm.has_permission(make_request(Role.VIEWER), MagicMock()) is False

    def test_unauthenticated_denied(self) -> None:
        perm = IsAnalystOrAbove()
        req = make_request(Role.ANALYST, authenticated=False)
        assert perm.has_permission(req, MagicMock()) is False


class TestReadOnly:
    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_allowed(self, method: str) -> None:
        perm = ReadOnly()
        request = MagicMock()
        request.method = method
        assert perm.has_permission(request, MagicMock()) is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_unsafe_methods_denied(self, method: str) -> None:
        perm = ReadOnly()
        request = MagicMock()
        request.method = method
        assert perm.has_permission(request, MagicMock()) is False


class TestRoleHierarchyIsOrdered:
    """Validate that role hierarchy is consistent across permission classes."""

    def test_admin_passes_all_checks(self) -> None:
        request = make_request(Role.ADMIN)
        view = MagicMock()
        assert IsAdmin().has_permission(request, view) is True
        assert IsAuditorOrAbove().has_permission(request, view) is True
        assert IsAnalystOrAbove().has_permission(request, view) is True

    def test_auditor_passes_auditor_and_analyst_but_not_admin(self) -> None:
        request = make_request(Role.AUDITOR)
        view = MagicMock()
        assert IsAdmin().has_permission(request, view) is False
        assert IsAuditorOrAbove().has_permission(request, view) is True
        assert IsAnalystOrAbove().has_permission(request, view) is True

    def test_analyst_passes_only_analyst_check(self) -> None:
        request = make_request(Role.ANALYST)
        view = MagicMock()
        assert IsAdmin().has_permission(request, view) is False
        assert IsAuditorOrAbove().has_permission(request, view) is False
        assert IsAnalystOrAbove().has_permission(request, view) is True

    def test_viewer_passes_no_elevated_check(self) -> None:
        request = make_request(Role.VIEWER)
        view = MagicMock()
        assert IsAdmin().has_permission(request, view) is False
        assert IsAuditorOrAbove().has_permission(request, view) is False
        assert IsAnalystOrAbove().has_permission(request, view) is False
