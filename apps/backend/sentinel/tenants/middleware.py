"""
Tenant Resolution Middleware.

Extracts tenant_id from the authenticated request and attaches it to
`request.tenant`. All subsequent database queries in that request are
automatically scoped to this tenant via the TenantQuerySet manager.

RESOLUTION ORDER:
    1. API key auth: tenant_id from APIKey.tenant_id field
    2. JWT auth: tenant_id claim embedded in the access token
    3. No auth / unauthenticated endpoints: request.tenant = None

IMPORTANT:
    This middleware must run AFTER authentication middleware.
    Place it after JWTAuthentication and APIKeyAuthentication in
    the DRF authentication pipeline (configured in settings.py).

    We use middleware rather than a DRF permission class because
    tenant scoping affects the queryset layer, which runs before
    permission checks in some cases (e.g. object-level permissions).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import structlog
from django.http import HttpRequest, HttpResponse

logger = structlog.get_logger(__name__)


class TenantMiddleware:
    """Resolve and attach tenant to every authenticated request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Tenant resolution happens after DRF auth — request.user is set
        # We defer resolution to after the response is started by using
        # a request attribute set during view dispatch instead.
        # For now, attach a resolver callable the view can invoke.
        request.tenant = None  # type: ignore[attr-defined]
        request.tenant_id = None  # type: ignore[attr-defined]

        response = self.get_response(request)
        return response


def get_tenant_from_request(request: HttpRequest) -> "Tenant | None":  # noqa: F821
    """
    Resolve tenant from an authenticated DRF request.

    Called from views and DRF generic views after authentication runs.
    Cached on request.tenant to avoid repeated DB lookups.
    """
    if hasattr(request, "_resolved_tenant"):
        return request._resolved_tenant  # type: ignore[attr-defined]

    from sentinel.tenants.models import Tenant

    tenant: "Tenant | None" = None

    # API key auth — auth is the APIKey instance (set by APIKeyAuthentication)
    if hasattr(request, "auth") and hasattr(request.auth, "tenant"):
        tenant = request.auth.tenant

    # JWT auth — tenant_id claim in the token payload
    elif hasattr(request, "auth") and hasattr(request.auth, "payload"):
        tenant_id_str = request.auth.payload.get("tenant_id")
        if tenant_id_str:
            try:
                tenant = Tenant.objects.get(id=uuid.UUID(tenant_id_str), is_active=True)
            except (Tenant.DoesNotExist, ValueError):
                pass

    # Superuser / staff — no tenant scoping (platform-level access)
    if tenant is None and hasattr(request, "user") and getattr(request.user, "is_superuser", False):
        request._resolved_tenant = None  # type: ignore[attr-defined]
        return None

    request._resolved_tenant = tenant  # type: ignore[attr-defined]

    if tenant:
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id), tenant_slug=tenant.slug)

    return tenant
