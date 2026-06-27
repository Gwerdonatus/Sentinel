"""
Health Check Functions.

Each check function returns a CheckResult with a status, latency, and optional message.
Checks must be fast (< 50ms each) and must never raise exceptions —
failure is returned as CheckStatus.ERROR, not raised.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    latency_ms: float
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status.value,
            "latency_ms": self.latency_ms,
        }
        if self.message:
            result["message"] = self.message
        if self.metadata:
            result["metadata"] = self.metadata
        return result


def check_database() -> CheckResult:
    """Verify PostgreSQL is reachable and responsive."""
    from django.db import connection

    start = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return CheckResult(
            name="database",
            status=CheckStatus.OK,
            latency_ms=latency_ms,
            metadata={"vendor": connection.vendor},
        )
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return CheckResult(
            name="database",
            status=CheckStatus.ERROR,
            latency_ms=latency_ms,
            message=f"Database unreachable: {type(e).__name__}",
        )


def check_redis() -> CheckResult:
    """Verify Redis is reachable and responsive."""
    from django.core.cache import cache

    start = time.perf_counter()
    try:
        probe_key = "sentinel:health:probe"
        cache.set(probe_key, "1", timeout=10)
        result = cache.get(probe_key)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        if result != "1":
            return CheckResult(
                name="redis",
                status=CheckStatus.DEGRADED,
                latency_ms=latency_ms,
                message="Redis write/read mismatch",
            )

        return CheckResult(
            name="redis",
            status=CheckStatus.OK,
            latency_ms=latency_ms,
        )
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return CheckResult(
            name="redis",
            status=CheckStatus.ERROR,
            latency_ms=latency_ms,
            message=f"Redis unreachable: {type(e).__name__}",
        )


def check_celery() -> CheckResult:
    """Verify at least one Celery worker is registered and responsive."""
    from config.celery import app as celery_app

    start = time.perf_counter()
    try:
        # ping() with timeout — don't wait forever for a degraded worker
        inspector = celery_app.control.inspect(timeout=1.0)
        ping_result = inspector.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        if not ping_result:
            return CheckResult(
                name="celery",
                status=CheckStatus.DEGRADED,
                latency_ms=latency_ms,
                message="No Celery workers responded to ping",
            )

        worker_count = len(ping_result)
        return CheckResult(
            name="celery",
            status=CheckStatus.OK,
            latency_ms=latency_ms,
            metadata={"active_workers": worker_count},
        )
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return CheckResult(
            name="celery",
            status=CheckStatus.ERROR,
            latency_ms=latency_ms,
            message=f"Celery broker unreachable: {type(e).__name__}",
        )
