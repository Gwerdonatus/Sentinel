"""
Sentinel RBAC Permission Classes.

DRF permission classes for role-based access control.
Used on views with `permission_classes = [IsAuthenticated, IsAdmin]`.

Role hierarchy (highest to lowest privilege):
    ADMIN   > AUDITOR > ANALYST > VIEWER

Design:
    Each class checks `request.user.role` directly — no DB query needed
    because the role is embedded in the JWT access token payload.
    This makes authorization checks O(1) with no network round-trip.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from sentinel.auth_service.models import Role


class IsAdmin(BasePermission):
    """Grants access only to ADMIN role users."""

    message = "Administrator role required."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.ADMIN  # type: ignore[union-attr]
        )


class IsAuditorOrAbove(BasePermission):
    """Grants access to AUDITOR and ADMIN roles."""

    message = "Auditor role or above required."

    _allowed = {Role.ADMIN, Role.AUDITOR}

    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self._allowed  # type: ignore[union-attr]
        )


class IsAnalystOrAbove(BasePermission):
    """Grants access to ANALYST, AUDITOR, and ADMIN roles."""

    message = "Analyst role or above required."

    _allowed = {Role.ADMIN, Role.AUDITOR, Role.ANALYST}

    def has_permission(self, request: Request, view: APIView) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self._allowed  # type: ignore[union-attr]
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Grants access if the requesting user owns the resource,
    or if they are an ADMIN.

    Requires the view or model to have a `user` or `actor` field.
    """

    message = "You do not have permission to access this resource."

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == Role.ADMIN:  # type: ignore[union-attr]
            return True
        # Check ownership
        owner = getattr(obj, "user", None) or getattr(obj, "actor", None)
        return owner == request.user


class ReadOnly(BasePermission):
    """Restricts to safe HTTP methods (GET, HEAD, OPTIONS)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.method in ("GET", "HEAD", "OPTIONS")


# Convenience composites
IsAuthenticatedAndAnalyst = [IsAuthenticated, IsAnalystOrAbove]
IsAuthenticatedAndAuditor = [IsAuthenticated, IsAuditorOrAbove]
IsAuthenticatedAndAdmin = [IsAuthenticated, IsAdmin]
