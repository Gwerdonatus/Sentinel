"""
Compliance Report Views.

POST /api/v1/compliance/reports/           — request a new report
GET  /api/v1/compliance/reports/           — list reports
GET  /api/v1/compliance/reports/{id}/      — report status
GET  /api/v1/compliance/reports/{id}/download/ — download the file
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from sentinel.auth_service.permissions import IsAuditorOrAbove
from sentinel.compliance.models import ComplianceReport, ReportStatus
from sentinel.compliance.serializers import (
    ComplianceReportRequestSerializer,
    ComplianceReportSerializer,
)
from sentinel.compliance.services import ComplianceReportService
from sentinel.core.exceptions.base import SentinelNotFoundError, SentinelValidationError

logger = structlog.get_logger(__name__)


class ComplianceReportListView(APIView):
    """GET/POST /api/v1/compliance/reports/"""

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        reports = ComplianceReport.objects.all().order_by("-created_at")[:50]
        return Response(ComplianceReportSerializer(reports, many=True).data)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = ComplianceReportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = ComplianceReportService()
        report = service.request_report(
            report_type=serializer.validated_data["report_type"],
            report_format=serializer.validated_data.get("report_format", "pdf"),
            from_dt=serializer.validated_data["from_dt"],
            to_dt=serializer.validated_data["to_dt"],
            filters=serializer.validated_data.get("filters", {}),
            requested_by=request.user,
        )

        return Response(
            ComplianceReportSerializer(report).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ComplianceReportDetailView(APIView):
    """GET /api/v1/compliance/reports/{id}/ — poll for status."""

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, report_id: str, *args: Any, **kwargs: Any) -> Response:
        report = self._get_report(report_id)
        return Response(ComplianceReportSerializer(report).data)

    @staticmethod
    def _get_report(report_id: str) -> ComplianceReport:
        try:
            return ComplianceReport.objects.get(id=uuid.UUID(report_id))
        except (ComplianceReport.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Report {report_id} not found.")


class ComplianceReportDownloadView(APIView):
    """GET /api/v1/compliance/reports/{id}/download/"""

    permission_classes = [IsAuthenticated, IsAuditorOrAbove]

    def get(self, request: Request, report_id: str, *args: Any, **kwargs: Any) -> FileResponse:
        from django.core.files.storage import default_storage
        from django.utils import timezone

        try:
            report = ComplianceReport.objects.get(id=uuid.UUID(report_id))
        except (ComplianceReport.DoesNotExist, ValueError):
            raise SentinelNotFoundError(f"Report {report_id} not found.")

        if report.status != ReportStatus.READY:
            raise SentinelValidationError(f"Report is not ready (status: {report.status}).")

        if report.expires_at and timezone.now() > report.expires_at:
            raise SentinelValidationError("This report has expired. Please generate a new one.")

        if not default_storage.exists(report.file_path):
            raise SentinelNotFoundError("Report file not found in storage.")

        logger.info(
            "compliance_report_downloaded",
            report_id=str(report.id),
            downloaded_by=str(request.user.id),  # type: ignore[union-attr]
        )

        content_types = {"pdf": "application/pdf", "csv": "text/csv", "json": "application/json"}
        file_handle = default_storage.open(report.file_path, "rb")
        response = FileResponse(
            file_handle,
            content_type=content_types.get(report.report_format, "application/octet-stream"),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="sentinel-{report.report_type}-{report.id}.{report.report_format}"'
        )
        return response
