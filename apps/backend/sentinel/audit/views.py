"""
Audit Ledger Views.

Endpoints:
    POST /api/v1/events/              — ingest an audit event
    GET  /api/v1/events/              — list events (filtered, cursor-paginated)
    GET  /api/v1/events/{id}/         — retrieve single event
    GET  /api/v1/events/{id}/verify/  — verify event signature integrity
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentinel.audit.models import AuditEventType
from sentinel.audit.serializers import (
    AuditEventFilterSerializer,
    AuditEventSerializer,
    AuditEventVerifySerializer,
)
from sentinel.audit.services import AuditEventService
from sentinel.auth_service.permissions import IsAnalystOrAbove, IsAuditorOrAbove
from sentinel.core.exceptions.base import SentinelNotFoundError, SentinelValidationError
from sentinel.core.pagination.cursor import CursorPagination

logger = structlog.get_logger(__name__)


class AuditEventIngestView(APIView):
    """
    POST /api/v1/events/

    Ingest a single audit event from an external system.
    Requires authentication — API key auth will replace this in Phase 3.
    Analysts and above can ingest events.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # Validate event_type is known
        event_type = request.data.get("event_type")
        if not event_type or event_type not in AuditEventType.values:
            raise SentinelValidationError(
                f"Unknown event_type. Must be one of: {', '.join(AuditEventType.values)}"
            )

        service = AuditEventService()
        event = service.record(
            event_type=event_type,
            actor_id=request.data.get("actor_id"),
            actor_email=request.data.get("actor_email", ""),
            actor_role=request.data.get("actor_role", ""),
            actor_ip=request.data.get("actor_ip", request.META.get("REMOTE_ADDR", "")),
            resource_type=request.data.get("resource_type", ""),
            resource_id=request.data.get("resource_id", ""),
            metadata=request.data.get("metadata", {}),
            request_id=getattr(request, "request_id", ""),
        )

        return Response(
            AuditEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )


class AuditEventListView(APIView):
    """
    GET /api/v1/events/?event_type=USER_LOGIN&actor_id=...&from_dt=...

    List audit events with optional filters.
    Cursor-paginated — never uses OFFSET.
    Auditors and above can access the full ledger.
    Analysts see only events they originated.
    """

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        filter_serializer = AuditEventFilterSerializer(data=request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        filters = filter_serializer.validated_data

        service = AuditEventService()
        queryset = service.list(
            actor_id=filters.get("actor_id"),
            event_type=filters.get("event_type"),
            resource_type=filters.get("resource_type"),
            resource_id=filters.get("resource_id"),
            request_id=filters.get("request_id"),
            from_dt=filters.get("from_dt"),
            to_dt=filters.get("to_dt"),
        )

        paginator = CursorPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = AuditEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AuditEventDetailView(APIView):
    """
    GET /api/v1/events/{id}/

    Retrieve a single audit event by ID.
    Auditors and above.
    """

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, event_id: str, *args: Any, **kwargs: Any) -> Response:
        try:
            parsed_id = uuid.UUID(event_id)
        except ValueError:
            raise SentinelValidationError(f"Invalid event ID format: {event_id}")

        service = AuditEventService()
        event = service.get(parsed_id)

        return Response(AuditEventSerializer(event).data)


class AuditEventVerifyView(APIView):
    """
    GET /api/v1/events/{id}/verify/

    Verify the HMAC signature of an audit event.
    Returns whether the event has been tampered with.
    Only ADMIN and AUDITOR can access this endpoint.
    """

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, event_id: str, *args: Any, **kwargs: Any) -> Response:
        try:
            parsed_id = uuid.UUID(event_id)
        except ValueError:
            raise SentinelValidationError(f"Invalid event ID format: {event_id}")

        service = AuditEventService()
        event = service.get(parsed_id)
        is_valid = service.verify_signature(event)

        logger.info(
            "audit_event_verified",
            event_id=str(event.id),
            is_valid=is_valid,
            verified_by=str(getattr(request.user, "id", None)),
        )

        return Response(
            AuditEventVerifySerializer({
                "event_id": event.id,
                "valid": is_valid,
                "message": "Signature valid — record unmodified." if is_valid
                           else "Signature INVALID — record may have been tampered with.",
            }).data,
            status=status.HTTP_200_OK,
        )
