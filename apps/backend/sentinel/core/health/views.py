"""
Sentinel Health Check Endpoints.

Provides two health endpoints used by load balancers, Kubernetes probes,
and monitoring systems:

GET /health/live/
    Liveness probe. Returns 200 if the Django process is running.
    Used by Kubernetes to know if the pod should be restarted.
    NEVER checks downstream dependencies here — if Redis is down,
    the app is still "alive" and should not be restarted.

GET /health/ready/
    Readiness probe. Returns 200 only if ALL dependencies are healthy.
    Used by load balancers to route traffic only to healthy instances.
    Returns 503 if any dependency is unavailable, removing the pod
    from the load balancer rotation without restarting it.

GET /health/
    Combined summary. Returns detailed status of all components.
    Used by Grafana, Slack alerting, and human operators.
    Returns 200 only if all checks pass.

These endpoints require no authentication — they are internal probes.
They must be fast (< 100ms) and must never block on slow operations.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views import View
from redis import ConnectionError as RedisConnectionError
from redis import Redis
from redis import TimeoutError as RedisTimeoutError

from sentinel.core.health.checks import (
    CheckResult,
    CheckStatus,
    check_celery,
    check_database,
    check_redis,
)

logger = structlog.get_logger(__name__)


class LivenessView(View):
    """
    Liveness probe — is this process alive?

    Always returns 200 if Django is running. Does not check dependencies.
    """

    def get(self, request: Any) -> JsonResponse:
        return JsonResponse({"status": "ok", "service": "sentinel"})


class ReadinessView(View):
    """
    Readiness probe — can this instance serve traffic?

    Checks all required dependencies. Returns 503 if any are unhealthy.
    This removes the instance from load balancer rotation without restarting it.
    """

    def get(self, request: Any) -> JsonResponse:
        checks = [
            check_database(),
            check_redis(),
        ]

        all_healthy = all(c.status == CheckStatus.OK for c in checks)
        http_status = 200 if all_healthy else 503

        return JsonResponse(
            {
                "status": "ready" if all_healthy else "not_ready",
                "checks": {c.name: c.to_dict() for c in checks},
            },
            status=http_status,
        )


class HealthSummaryView(View):
    """
    Full health summary — detailed component status.

    Checks all dependencies including optional ones (Celery).
    Used by monitoring dashboards, not by Kubernetes probes.
    """

    def get(self, request: Any) -> JsonResponse:
        start = time.perf_counter()

        checks = [
            check_database(),
            check_redis(),
            check_celery(),
        ]

        all_healthy = all(c.status == CheckStatus.OK for c in checks)
        total_ms = round((time.perf_counter() - start) * 1000, 2)
        http_status = 200 if all_healthy else 503

        if not all_healthy:
            logger.warning(
                "health_check_failed",
                checks={c.name: c.status.value for c in checks if c.status != CheckStatus.OK},
                total_ms=total_ms,
            )

        return JsonResponse(
            {
                "status": "healthy" if all_healthy else "degraded",
                "service": "sentinel",
                "version": "1.0.0",
                "checks": {c.name: c.to_dict() for c in checks},
                "total_ms": total_ms,
            },
            status=http_status,
        )
