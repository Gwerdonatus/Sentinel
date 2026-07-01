"""
Sentinel API v1 Views.

Phase 1 provides:
- GET /api/v1/ — API root with version info and available endpoint discovery
- GET /api/v1/ping/ — Simple connectivity check with auth bypass (useful for SDK clients)

These are the foundation views. Business endpoints are added in Phase 2+.
"""

from __future__ import annotations

from typing import Any

import structlog
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = structlog.get_logger(__name__)


class APIRootView(APIView):
    """
    API root — returns version info and available endpoint discovery.

    This endpoint is the entry point for SDK clients and API explorers.
    It does NOT require authentication so clients can discover the API
    before obtaining credentials.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        logger.info("api_root_accessed", ip=request.META.get("REMOTE_ADDR"))
        return Response(
            {
                "service": "sentinel",
                "version": "4.0.0",
                "api_version": "v1",
                "status": "operational",
                "timestamp": timezone.now().isoformat(),
                "documentation": "/api/schema/redoc/",
                "endpoints": {
                    "ping": request.build_absolute_uri("ping/"),
                    "health": request.build_absolute_uri("/health/"),
                    "schema": request.build_absolute_uri("/api/schema/"),
                    "auth": request.build_absolute_uri("auth/"),
                    "events": request.build_absolute_uri("events/"),
                    "alerts": request.build_absolute_uri("alerts/"),
                    "risk_summary": request.build_absolute_uri("risk/summary/"),
                    "api_keys": request.build_absolute_uri("api-keys/"),
                    "compliance_reports": request.build_absolute_uri("compliance/reports/"),
                },
                "features": {
                    "authentication": True,
                    "audit_ledger": True,
                    "ai_actor_tracking": True,
                    "risk_scoring": True,
                    "alerting": True,
                    "api_key_management": True,
                    "compliance_reports": True,
                    "dashboard": True,
                },
            }
        )


class PingView(APIView):
    """
    Ping endpoint — verifies API connectivity without full auth.

    Useful for:
    - SDK clients verifying they can reach the API
    - Network diagnostic checks
    - Load balancer health probes (alternative to /health/live/)

    Returns the server timestamp so clients can check clock skew.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(
            {
                "pong": True,
                "timestamp": timezone.now().isoformat(),
                "request_id": getattr(request, "request_id", None),
            }
        )
