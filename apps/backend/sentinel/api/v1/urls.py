"""
Sentinel API v1 URL Configuration.

All v1 endpoints live under /api/v1/.

See ADR-008 for the URL versioning strategy.
"""

from django.urls import path

from sentinel.api.v1.views import APIRootView, PingView

urlpatterns = [
    path("", APIRootView.as_view(), name="api-v1-root"),
    path("ping/", PingView.as_view(), name="api-v1-ping"),
    # Phase 2+
    # path("auth/", include("sentinel.auth_service.urls")),
    # path("events/", include("sentinel.audit.urls")),
    # path("alerts/", include("sentinel.risk.urls")),
]
