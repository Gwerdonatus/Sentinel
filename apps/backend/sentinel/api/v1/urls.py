"""Sentinel API v1 URL Configuration."""

from django.urls import include, path

from sentinel.api.v1.views import APIRootView, PingView

urlpatterns = [
    path("", APIRootView.as_view(), name="api-v1-root"),
    path("ping/", PingView.as_view(), name="api-v1-ping"),
    # Phase 2
    path("auth/", include("sentinel.auth_service.urls")),
    path("events/", include("sentinel.audit.urls")),
    # Phase 3
    path("", include("sentinel.risk.urls")),
    path("api-keys/", include("sentinel.api_keys.urls")),
]
