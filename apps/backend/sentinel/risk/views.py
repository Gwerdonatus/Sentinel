"""
Risk Intelligence Views.

GET  /api/v1/alerts/                       — list alerts (filtered, paginated)
GET  /api/v1/alerts/{id}/                  — alert detail
POST /api/v1/alerts/{id}/acknowledge/      — acknowledge an alert
POST /api/v1/alerts/{id}/resolve/          — resolve an alert
GET  /api/v1/alerts/rules/                 — list alert rules
POST /api/v1/alerts/rules/                 — create alert rule
DELETE /api/v1/alerts/rules/{id}/          — deactivate a rule

GET  /api/v1/risk/summary/                 — platform risk summary
GET  /api/v1/risk/actors/{actor_id}/       — actor risk profile
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentinel.auth_service.permissions import IsAdmin, IsAnalystOrAbove, IsAuditorOrAbove
from sentinel.core.exceptions.base import SentinelNotFoundError, SentinelValidationError
from sentinel.core.pagination.cursor import CursorPagination
from sentinel.risk.models import Alert, AlertRule, AlertStatus
from sentinel.risk.serializers import (
    AlertDetailSerializer,
    AlertListSerializer,
    AlertRuleSerializer,
    ResolveAlertSerializer,
    RiskSummarySerializer,
)

logger = structlog.get_logger(__name__)


class AlertListView(APIView):
    """GET /api/v1/alerts/ — list alerts with filters."""

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        qs = Alert.objects.select_related("rule").order_by("-created_at")

        # Filter params
        status_filter = request.query_params.get("status")
        severity_filter = request.query_params.get("severity")
        actor_type_filter = request.query_params.get("actor_type")
        agent_name_filter = request.query_params.get("agent_name")

        if status_filter:
            qs = qs.filter(status=status_filter)
        if severity_filter:
            qs = qs.filter(severity=severity_filter)
        if actor_type_filter:
            qs = qs.filter(actor_type=actor_type_filter)
        if agent_name_filter:
            qs = qs.filter(agent_name=agent_name_filter)

        paginator = CursorPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AlertListSerializer(page, many=True).data)


class AlertDetailView(APIView):
    """GET /api/v1/alerts/{id}/"""

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get(self, request: Request, alert_id: str, *args: Any, **kwargs: Any) -> Response:
        alert = self._get_alert(alert_id)
        return Response(AlertDetailSerializer(alert).data)

    @staticmethod
    def _get_alert(alert_id: str) -> Alert:
        try:
            return Alert.objects.select_related("rule", "acknowledged_by").get(
                id=uuid.UUID(alert_id)
            )
        except (Alert.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Alert {alert_id} not found.")


class AlertAcknowledgeView(APIView):
    """POST /api/v1/alerts/{id}/acknowledge/"""

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def post(self, request: Request, alert_id: str, *args: Any, **kwargs: Any) -> Response:
        try:
            alert = Alert.objects.get(id=uuid.UUID(alert_id))
        except (Alert.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Alert {alert_id} not found.")

        if alert.status != AlertStatus.OPEN:
            raise SentinelValidationError(
                f"Alert is already {alert.status}. Only OPEN alerts can be acknowledged."
            )

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = request.user  # type: ignore[assignment]
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at", "updated_at"])

        logger.info(
            "alert_acknowledged",
            alert_id=str(alert.id),
            acknowledged_by=str(request.user.id),  # type: ignore[union-attr]
        )

        return Response(AlertDetailSerializer(alert).data)


class AlertResolveView(APIView):
    """POST /api/v1/alerts/{id}/resolve/"""

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def post(self, request: Request, alert_id: str, *args: Any, **kwargs: Any) -> Response:
        serializer = ResolveAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            alert = Alert.objects.get(id=uuid.UUID(alert_id))
        except (Alert.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Alert {alert_id} not found.")

        if alert.status == AlertStatus.RESOLVED:
            raise SentinelValidationError("Alert is already resolved.")

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = timezone.now()
        alert.resolution_note = serializer.validated_data.get("note", "")
        alert.save(update_fields=["status", "resolved_at", "resolution_note", "updated_at"])

        logger.info(
            "alert_resolved",
            alert_id=str(alert.id),
            resolved_by=str(request.user.id),  # type: ignore[union-attr]
        )

        return Response(AlertDetailSerializer(alert).data)


class AlertRuleListView(APIView):
    """GET/POST /api/v1/alerts/rules/"""

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        rules = AlertRule.objects.all().order_by("-created_at")
        return Response(AlertRuleSerializer(rules, many=True).data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        if not (request.user.is_authenticated and request.user.role in ("ADMIN", "ANALYST")):  # type: ignore[union-attr]
            raise SentinelNotFoundError("Only ADMIN or ANALYST roles can create alert rules.")

        serializer = AlertRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save(created_by=request.user)
        return Response(AlertRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class AlertRuleDetailView(APIView):
    """DELETE /api/v1/alerts/rules/{id}/ — deactivate a rule"""

    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request: Request, rule_id: str, *args: Any, **kwargs: Any) -> Response:
        try:
            rule = AlertRule.objects.get(id=uuid.UUID(rule_id))
        except (AlertRule.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Alert rule {rule_id} not found.")

        if rule.is_builtin:
            raise SentinelValidationError(
                "Built-in rules cannot be deleted. Deactivate them instead."
            )

        rule.is_active = False
        rule.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RiskSummaryView(APIView):
    """
    GET /api/v1/risk/summary/

    Platform-wide risk summary: open alerts by severity, top risky actors,
    recent critical events. Used by the dashboard home screen.
    """

    permission_classes = [IsAuthenticated, IsAnalystOrAbove]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.db.models import Count
        from sentinel.audit.models import AuditEvent

        now = timezone.now()
        last_24h = now - timezone.timedelta(hours=24)

        open_alerts = Alert.objects.filter(status=AlertStatus.OPEN)

        summary = {
            "open_alerts": {
                "total": open_alerts.count(),
                "critical": open_alerts.filter(severity="critical").count(),
                "high": open_alerts.filter(severity="high").count(),
                "medium": open_alerts.filter(severity="medium").count(),
                "low": open_alerts.filter(severity="low").count(),
            },
            "last_24h": {
                "total_events": AuditEvent.objects.filter(created_at__gte=last_24h).count(),
                "ai_agent_events": AuditEvent.objects.filter(
                    created_at__gte=last_24h, actor_type="AI_AGENT"
                ).count(),
                "high_risk_events": AuditEvent.objects.filter(
                    created_at__gte=last_24h, risk_score__gte=50
                ).count(),
                "new_alerts": Alert.objects.filter(created_at__gte=last_24h).count(),
            },
            "top_risky_ai_agents": list(
                AuditEvent.objects.filter(
                    created_at__gte=last_24h,
                    actor_type="AI_AGENT",
                    risk_score__gte=25,
                )
                .exclude(agent_name="")
                .values("agent_name")
                .annotate(
                    event_count=Count("id"),
                )
                .order_by("-event_count")[:5]
            ),
        }

        return Response(summary)


class ActorRiskProfileView(APIView):
    """
    GET /api/v1/risk/actors/{actor_id}/

    Risk profile for a specific actor — recent events, risk score history,
    open alerts. Works for humans and AI agents alike.
    """

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, actor_id: str, *args: Any, **kwargs: Any) -> Response:
        from sentinel.audit.models import AuditEvent

        try:
            parsed_id = uuid.UUID(actor_id)
        except ValueError:
            raise SentinelValidationError(f"Invalid actor ID: {actor_id}")

        last_30d = timezone.now() - timezone.timedelta(days=30)

        events = AuditEvent.objects.filter(
            actor_id=parsed_id, created_at__gte=last_30d
        ).order_by("-created_at")

        if not events.exists():
            raise SentinelNotFoundError(f"No events found for actor {actor_id}")

        latest = events.first()
        scores = list(
            events.exclude(risk_score__isnull=True)
            .values_list("risk_score", flat=True)[:100]
        )
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0

        open_alerts = Alert.objects.filter(
            actor_id=parsed_id, status=AlertStatus.OPEN
        ).count()

        return Response({
            "actor_id": actor_id,
            "actor_type": getattr(latest, "actor_type", "HUMAN"),
            "actor_email": latest.actor_email,
            "agent_name": getattr(latest, "agent_name", ""),
            "last_30_days": {
                "total_events": events.count(),
                "avg_risk_score": round(avg_score, 1),
                "max_risk_score": max_score,
                "open_alerts": open_alerts,
            },
            "recent_events": [
                {
                    "id": str(e.id),
                    "event_type": e.event_type,
                    "risk_score": e.risk_score,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events[:10]
            ],
        })
