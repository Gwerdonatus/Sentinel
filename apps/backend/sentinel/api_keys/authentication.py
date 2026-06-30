"""
API Key Authentication Backend.

DRF authentication class that validates Bearer tokens against the APIKey table.
Used by services and AI agents to authenticate with Sentinel.

Header format:
    Authorization: Bearer sk_live_xxxxx

On successful authentication:
    - Returns (api_key, None) — api_key is the APIKey instance
    - Updates last_used_at and total_uses on the key
    - The request.user is set to the APIKey's created_by user (for RBAC),
      or AnonymousUser if the key has no owner

The audit system reads actor_type and agent_name from request.auth (the APIKey)
to populate audit events correctly.
"""

from __future__ import annotations

import structlog
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from sentinel.api_keys.models import APIKey

logger = structlog.get_logger(__name__)


class APIKeyAuthentication(BaseAuthentication):
    """Authenticate requests using Bearer API keys."""

    keyword = "Bearer"

    def authenticate(self, request: Request) -> tuple[object, APIKey] | None:
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith(f"{self.keyword} "):
            return None  # Not an API key request — try next authenticator

        presented_key = auth_header[len(self.keyword) + 1:].strip()

        if not presented_key:
            return None

        # Skip JWT tokens (they start with eyJ)
        if presented_key.startswith("eyJ"):
            return None

        api_key = APIKey.verify_key(presented_key)

        if api_key is None:
            logger.warning(
                "api_key_auth_failed",
                key_prefix=presented_key[:12] if len(presented_key) >= 12 else "short",
                ip=request.META.get("REMOTE_ADDR"),
            )
            raise AuthenticationFailed("Invalid or expired API key.")

        ip = request.META.get("REMOTE_ADDR", "")
        api_key.record_usage(ip_address=ip)

        logger.info(
            "api_key_authenticated",
            key_id=str(api_key.id),
            key_name=api_key.name,
            actor_type=api_key.actor_type,
            agent_name=api_key.agent_name or None,
            ip=ip,
        )

        # Return the key's owner as the user (for admin RBAC),
        # or None if the key has no human owner (pure service/AI keys)
        user = api_key.created_by
        return user, api_key

    def authenticate_header(self, request: Request) -> str:
        return f'{self.keyword} realm="Sentinel API"'
