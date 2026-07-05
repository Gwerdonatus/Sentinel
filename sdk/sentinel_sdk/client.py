"""
Sentinel Python SDK.

Send security and audit events from any Python service to Sentinel.

SYNC USAGE:
    from sentinel_sdk import SentinelClient

    client = SentinelClient(
        api_key="sk_live_...",
        base_url="https://sentinel.your-company.com",
    )

    # Record a simple event
    client.record("USER_LOGIN", actor_email="user@company.com")

    # Record an event from an AI agent
    client.record(
        "TRANSFER_INITIATED",
        resource_type="transfer",
        resource_id=transfer_id,
        metadata={"amount": 5000, "currency": "NGN"},
    )

ASYNC USAGE:
    from sentinel_sdk import AsyncSentinelClient

    async with AsyncSentinelClient(api_key="sk_live_...") as client:
        await client.record("USER_LOGIN", actor_email="user@company.com")

CONTEXT MANAGER (sync):
    with SentinelClient(api_key="sk_live_...") as client:
        client.record("USER_LOGIN")

CONFIGURATION:
    api_key      — Required. Your sk_live_ or sk_test_ key.
    base_url     — Sentinel instance URL. Default: https://api.sentinel.io
    timeout      — Request timeout in seconds. Default: 5.0
    fail_silent  — If True, network errors are logged but not raised. Default: True
                   Set to False in tests to catch integration issues early.
    actor_type   — Default actor type for all events from this client.
                   "HUMAN_API" | "SERVICE" | "AI_AGENT". Default: "SERVICE"
    agent_name   — For AI_AGENT keys: the agent's name. Set once, applied to all events.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

__version__ = "0.5.0"
__all__ = ["SentinelClient", "AsyncSentinelClient", "SentinelSDKError"]


class SentinelSDKError(Exception):
    """Raised when Sentinel returns an error and fail_silent=False."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class SentinelClient:
    """
    Synchronous Sentinel SDK client.

    Thread-safe. Reuse across requests — the underlying httpx.Client
    maintains a connection pool.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 5.0,
        fail_silent: bool = True,
        actor_type: str = "SERVICE",
        agent_name: str = "",
    ) -> None:
        self._api_key = api_key or os.environ.get("SENTINEL_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Sentinel API key is required. Pass api_key= or set SENTINEL_API_KEY env var."
            )

        self._base_url = (base_url or os.environ.get("SENTINEL_BASE_URL", "https://api.sentinel.io")).rstrip("/")
        self._timeout = timeout
        self._fail_silent = fail_silent
        self._actor_type = actor_type
        self._agent_name = agent_name

        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"sentinel-sdk-python/{__version__}",
            },
            timeout=timeout,
        )

    def record(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        actor_email: str = "",
        actor_role: str = "",
        actor_ip: str = "",
        resource_type: str = "",
        resource_id: str = "",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Record an audit event.

        Returns the created event dict on success, or None if fail_silent=True
        and the request fails.

        Args:
            event_type:    Required. One of the AuditEventType values.
                           e.g. "USER_LOGIN", "TRANSFER_INITIATED", "ADMIN_ACTION"
            actor_id:      UUID of the actor performing the action.
            actor_email:   Email of the actor (human events).
            actor_role:    Role of the actor at time of event.
            actor_ip:      IP address of the actor.
            resource_type: Type of resource affected. e.g. "transfer", "user", "api_key"
            resource_id:   Identifier of the specific resource.
            metadata:      Arbitrary context dict. JSON-serializable values only.
            request_id:    X-Request-ID to correlate with your service's own logs.
        """
        payload: dict[str, Any] = {
            "event_type": event_type,
            "actor_type": self._actor_type,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "actor_ip": actor_ip,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "request_id": request_id or str(uuid.uuid4()),
        }
        if actor_id:
            payload["actor_id"] = actor_id
        if self._agent_name:
            payload["agent_name"] = self._agent_name

        return self._post("/api/v1/events/ingest/", payload)

    def health(self) -> dict[str, Any] | None:
        """Check Sentinel connectivity and health."""
        try:
            response = self._client.get("/health/live/")
            return response.json()
        except Exception as exc:
            logger.error("sentinel_health_check_failed", error=str(exc))
            return None

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        start = time.perf_counter()
        try:
            response = self._client.post(path, json=payload)
            latency_ms = round((time.perf_counter() - start) * 1000, 1)

            if response.status_code in (200, 201):
                logger.debug(
                    "sentinel_event_recorded",
                    event_type=payload.get("event_type"),
                    latency_ms=latency_ms,
                )
                return response.json()

            error_body = response.json()
            error_msg = error_body.get("error", {}).get("message", "Unknown error")
            logger.error(
                "sentinel_event_failed",
                event_type=payload.get("event_type"),
                status_code=response.status_code,
                error=error_msg,
            )
            if not self._fail_silent:
                raise SentinelSDKError(error_msg, status_code=response.status_code)
            return None

        except SentinelSDKError:
            raise
        except Exception as exc:
            logger.error(
                "sentinel_request_failed",
                event_type=payload.get("event_type"),
                error=str(exc),
            )
            if not self._fail_silent:
                raise SentinelSDKError(str(exc)) from exc
            return None

    def __enter__(self) -> "SentinelClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()


class AsyncSentinelClient:
    """
    Async Sentinel SDK client.

    Use with async/await in FastAPI, async Django views, or any async context.
    Use as an async context manager for automatic connection cleanup.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 5.0,
        fail_silent: bool = True,
        actor_type: str = "SERVICE",
        agent_name: str = "",
    ) -> None:
        self._api_key = api_key or os.environ.get("SENTINEL_API_KEY", "")
        if not self._api_key:
            raise ValueError("Sentinel API key is required.")

        self._base_url = (base_url or os.environ.get("SENTINEL_BASE_URL", "https://api.sentinel.io")).rstrip("/")
        self._timeout = timeout
        self._fail_silent = fail_silent
        self._actor_type = actor_type
        self._agent_name = agent_name

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"sentinel-sdk-python/{__version__}",
            },
            timeout=timeout,
        )

    async def record(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        actor_email: str = "",
        actor_role: str = "",
        actor_ip: str = "",
        resource_type: str = "",
        resource_id: str = "",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Async version of record(). Identical signature."""
        payload: dict[str, Any] = {
            "event_type": event_type,
            "actor_type": self._actor_type,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "actor_ip": actor_ip,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "request_id": request_id or str(uuid.uuid4()),
        }
        if actor_id:
            payload["actor_id"] = actor_id
        if self._agent_name:
            payload["agent_name"] = self._agent_name

        return await self._post("/api/v1/events/ingest/", payload)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = await self._client.post(path, json=payload)
            if response.status_code in (200, 201):
                return response.json()

            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            logger.error("sentinel_async_event_failed", status_code=response.status_code, error=error_msg)
            if not self._fail_silent:
                raise SentinelSDKError(error_msg, status_code=response.status_code)
            return None

        except SentinelSDKError:
            raise
        except Exception as exc:
            logger.error("sentinel_async_request_failed", error=str(exc))
            if not self._fail_silent:
                raise SentinelSDKError(str(exc)) from exc
            return None

    async def __aenter__(self) -> "AsyncSentinelClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()
