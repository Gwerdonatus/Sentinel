"""
Sentinel URL Configuration.

URL structure:
    /health/          — Liveness and readiness probes
    /api/v1/          — REST API version 1
    /api/schema/      — OpenAPI schema (development only)
    /admin/           — Django admin
    /metrics          — Prometheus metrics (internal)
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Health checks — no auth required, used by load balancers
    path("health/", include("sentinel.core.urls.health")),
    # API v1
    path("api/v1/", include("sentinel.api.v1.urls")),
    # Django admin
    path("admin/", admin.site.urls),
    # Prometheus metrics (Prometheus scrapes this endpoint)
    path("", include("django_prometheus.urls")),
]

# OpenAPI schema — development and staging only
if settings.ENVIRONMENT in ("development", "staging"):
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
        path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]

# Customize admin branding
admin.site.site_header = "Sentinel Administration"
admin.site.site_title = "Sentinel"
admin.site.index_title = "Security Platform Administration"
