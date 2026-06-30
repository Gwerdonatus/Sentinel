"""API Key Views."""

from __future__ import annotations

from typing import Any

import structlog
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentinel.api_keys.models import APIKey
from sentinel.api_keys.serializers import (
    APIKeyCreateSerializer,
    APIKeyResponseSerializer,
    APIKeyCreatedResponseSerializer,
)
from sentinel.api_keys.services import APIKeyService
from sentinel.auth_service.permissions import IsAdmin
from sentinel.core.exceptions.base import SentinelNotFoundError

logger = structlog.get_logger(__name__)


class APIKeyListView(APIView):
    """GET /api/v1/api-keys/ — list API keys (no secrets exposed)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        keys = APIKey.objects.filter(deleted_at__isnull=True).order_by("-created_at")
        return Response(APIKeyResponseSerializer(keys, many=True).data)


class APIKeyCreateView(APIView):
    """POST /api/v1/api-keys/create/ — create key (full key shown once)."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = APIKeyService()
        api_key, full_key = service.create(
            name=serializer.validated_data["name"],
            actor_type=serializer.validated_data["actor_type"],
            scopes=serializer.validated_data["scopes"],
            created_by=request.user,
            environment=serializer.validated_data.get("environment", "live"),
            agent_name=serializer.validated_data.get("agent_name", ""),
            agent_version=serializer.validated_data.get("agent_version", ""),
            agent_description=serializer.validated_data.get("agent_description", ""),
            expires_in_days=serializer.validated_data.get("expires_in_days"),
        )

        response_data = APIKeyResponseSerializer(api_key).data
        response_data["key"] = full_key  # Shown ONCE

        return Response(response_data, status=status.HTTP_201_CREATED)


class APIKeyDetailView(APIView):
    """
    GET    /api/v1/api-keys/{id}/          — key detail
    POST   /api/v1/api-keys/{id}/rotate/   — rotate key
    DELETE /api/v1/api-keys/{id}/          — revoke key
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request: Request, key_id: str, *args: Any, **kwargs: Any) -> Response:
        try:
            key = APIKey.objects.get(id=key_id, deleted_at__isnull=True)
        except APIKey.DoesNotExist:
            raise SentinelNotFoundError(f"API key {key_id} not found.")
        return Response(APIKeyResponseSerializer(key).data)

    def delete(self, request: Request, key_id: str, *args: Any, **kwargs: Any) -> Response:
        service = APIKeyService()
        service.revoke(key_id, requesting_user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
