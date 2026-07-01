"""
Compliance Report Generation Service.

Builds evidence packages from the audit ledger. The defining feature
relative to a generic "export the logs" tool: every report's summary
section explicitly breaks down activity by actor_type, and lists every
named AI agent that took action in the reporting period.

This is the concrete answer to the question from Post 1: "can we prove
what an AI agent did, in a format a regulator or auditor can consume."

PDF generation uses a simple HTML-to-structure approach with reportlab
for layout control — chosen because compliance documents need precise,
predictable pagination, not a browser rendering engine in the loop.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime

import structlog
from django.conf import settings
from django.db.models import Count, QuerySet
from django.utils import timezone

from sentinel.compliance.models import ComplianceReport, ReportStatus

logger = structlog.get_logger(__name__)


class ComplianceReportService:
    """Generates compliance evidence reports from the audit ledger."""

    def request_report(
        self,
        report_type: str,
        report_format: str,
        from_dt: datetime,
        to_dt: datetime,
        filters: dict[str, object],
        requested_by: object,
    ) -> ComplianceReport:
        """Create a pending report record and dispatch generation task."""
        report = ComplianceReport.objects.create(
            report_type=report_type,
            report_format=report_format,
            from_dt=from_dt,
            to_dt=to_dt,
            filters=filters,
            requested_by=requested_by,
            status=ReportStatus.PENDING,
        )

        from sentinel.compliance.tasks import generate_report_task
        generate_report_task.delay(str(report.id))

        logger.info(
            "compliance_report_requested",
            report_id=str(report.id),
            report_type=report_type,
            requested_by=str(getattr(requested_by, "id", None)),
        )

        return report

    def generate(self, report_id: str) -> None:
        """
        Generate the report file. Called from the async task.
        Updates report status throughout: PENDING -> GENERATING -> READY/FAILED.
        """
        from sentinel.audit.models import AuditEvent

        try:
            report = ComplianceReport.objects.get(id=uuid.UUID(report_id))
        except ComplianceReport.DoesNotExist:
            logger.error("compliance_report_not_found", report_id=report_id)
            return

        report.status = ReportStatus.GENERATING
        report.save(update_fields=["status", "updated_at"])

        try:
            events = self._build_queryset(report)
            summary = self._build_summary(events)

            if report.report_format == "pdf":
                file_bytes, file_path = self._render_pdf(report, events, summary)
            elif report.report_format == "csv":
                file_bytes, file_path = self._render_csv(report, events)
            else:  # json
                file_bytes, file_path = self._render_json(report, events, summary)

            report.summary = summary
            report.file_path = file_path
            report.file_size_bytes = len(file_bytes)
            report.status = ReportStatus.READY
            report.generated_at = timezone.now()
            report.expires_at = timezone.now() + timezone.timedelta(days=30)
            report.save()

            logger.info(
                "compliance_report_generated",
                report_id=str(report.id),
                total_events=summary["total_events"],
                file_size_bytes=report.file_size_bytes,
            )

        except Exception as exc:
            report.status = ReportStatus.FAILED
            report.error_message = str(exc)
            report.save(update_fields=["status", "error_message", "updated_at"])
            logger.error(
                "compliance_report_generation_failed",
                report_id=str(report.id),
                error=str(exc),
                exc_info=True,
            )
            raise

    def _build_queryset(self, report: ComplianceReport) -> "QuerySet":
        from sentinel.audit.models import AuditEvent

        qs = AuditEvent.objects.filter(
            created_at__gte=report.from_dt,
            created_at__lte=report.to_dt,
        )

        f = report.filters
        if f.get("event_type"):
            qs = qs.filter(event_type=f["event_type"])
        if f.get("actor_type"):
            qs = qs.filter(actor_type=f["actor_type"])
        if f.get("resource_type"):
            qs = qs.filter(resource_type=f["resource_type"])
        if f.get("agent_name"):
            qs = qs.filter(agent_name=f["agent_name"])

        return qs.order_by("created_at")

    def _build_summary(self, events: "QuerySet") -> dict[str, object]:
        """
        Build the summary section — the AI-attribution-forward part of the report.

        This is what makes a Sentinel report different from a raw log export:
        actor_type breakdown is the headline, not an afterthought.
        """
        total = events.count()

        by_actor_type = dict(
            events.values("actor_type").annotate(count=Count("id")).values_list("actor_type", "count")
        )

        ai_agents = list(
            events.exclude(agent_name="")
            .filter(actor_type="AI_AGENT")
            .values("agent_name")
            .annotate(event_count=Count("id"))
            .order_by("-event_count")
        )

        high_risk_count = events.filter(risk_score__gte=50).count()

        by_event_type = dict(
            events.values("event_type").annotate(count=Count("id")).order_by("-count")[:10]
            .values_list("event_type", "count")
        )

        return {
            "total_events": total,
            "by_actor_type": by_actor_type,
            "ai_agents_involved": ai_agents,
            "high_risk_event_count": high_risk_count,
            "top_event_types": by_event_type,
            "generated_at": timezone.now().isoformat(),
        }

    def _render_csv(self, report: ComplianceReport, events: "QuerySet") -> tuple[bytes, str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            "Timestamp", "Event Type", "Actor Type", "Actor Email",
            "Agent Name", "Resource Type", "Resource ID", "Risk Score", "Request ID",
        ])
        for e in events.iterator(chunk_size=1000):
            writer.writerow([
                e.created_at.isoformat(), e.event_type, e.actor_type,
                e.actor_email, e.agent_name, e.resource_type,
                e.resource_id, e.risk_score or "", e.request_id,
            ])

        content = buffer.getvalue().encode("utf-8")
        file_path = f"compliance-reports/{report.id}.csv"
        self._save_file(file_path, content)
        return content, file_path

    def _render_json(
        self, report: ComplianceReport, events: "QuerySet", summary: dict
    ) -> tuple[bytes, str]:
        payload = {
            "report_id": str(report.id),
            "report_type": report.report_type,
            "period": {"from": report.from_dt.isoformat(), "to": report.to_dt.isoformat()},
            "summary": summary,
            "events": [
                {
                    "id": str(e.id),
                    "created_at": e.created_at.isoformat(),
                    "event_type": e.event_type,
                    "actor_type": e.actor_type,
                    "actor_email": e.actor_email,
                    "agent_name": e.agent_name,
                    "resource_type": e.resource_type,
                    "resource_id": e.resource_id,
                    "risk_score": e.risk_score,
                    "request_id": e.request_id,
                    "signature": e.signature,
                }
                for e in events.iterator(chunk_size=1000)
            ],
        }
        content = json.dumps(payload, indent=2).encode("utf-8")
        file_path = f"compliance-reports/{report.id}.json"
        self._save_file(file_path, content)
        return content, file_path

    def _render_pdf(
        self, report: ComplianceReport, events: "QuerySet", summary: dict
    ) -> tuple[bytes, str]:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("SentinelTitle", parent=styles["Title"], fontSize=20, spaceAfter=6)
        heading_style = ParagraphStyle("SentinelHeading", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8)

        elements: list[object] = []

        # Header
        elements.append(Paragraph(f"Sentinel Compliance Report — {report.get_report_type_display()}", title_style))
        elements.append(Paragraph(
            f"Period: {report.from_dt.strftime('%Y-%m-%d')} to {report.to_dt.strftime('%Y-%m-%d')}",
            styles["Normal"],
        ))
        elements.append(Paragraph(
            f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 0.3 * inch))

        # Summary — actor type breakdown is the headline
        elements.append(Paragraph("Activity Summary by Actor Type", heading_style))
        actor_rows = [["Actor Type", "Event Count"]]
        for actor_type, count in summary["by_actor_type"].items():
            actor_rows.append([actor_type, str(count)])
        actor_table = Table(actor_rows, colWidths=[3 * inch, 2 * inch])
        actor_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f5f5f5")),
        ]))
        elements.append(actor_table)

        # AI agent attribution — the distinguishing section
        if summary["ai_agents_involved"]:
            elements.append(Paragraph("AI Agents Involved", heading_style))
            ai_rows = [["Agent Name", "Event Count"]]
            for agent in summary["ai_agents_involved"]:
                ai_rows.append([agent["agent_name"], str(agent["event_count"])])
            ai_table = Table(ai_rows, colWidths=[3 * inch, 2 * inch])
            ai_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(ai_table)
            elements.append(Paragraph(
                f"Total high-risk events (score ≥ 50) in this period: {summary['high_risk_event_count']}",
                styles["Normal"],
            ))

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(f"Total Events: {summary['total_events']}", styles["Heading3"]))

        # Event detail table
        elements.append(PageBreak())
        elements.append(Paragraph("Event Detail", heading_style))
        detail_rows = [["Timestamp", "Event Type", "Actor", "Risk"]]
        for e in events.iterator(chunk_size=1000):
            actor_label = e.agent_name or e.actor_email or e.actor_type
            detail_rows.append([
                e.created_at.strftime("%Y-%m-%d %H:%M"),
                e.event_type,
                actor_label[:30],
                str(e.risk_score) if e.risk_score is not None else "-",
            ])
            if len(detail_rows) > 2000:  # Cap PDF size
                detail_rows.append(["...", "truncated", "...", "..."])
                break

        detail_table = Table(detail_rows, colWidths=[1.3 * inch, 1.8 * inch, 2.4 * inch, 0.6 * inch])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e1b4b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ]))
        elements.append(detail_table)

        doc.build(elements)
        content = buffer.getvalue()
        file_path = f"compliance-reports/{report.id}.pdf"
        self._save_file(file_path, content)
        return content, file_path

    @staticmethod
    def _save_file(file_path: str, content: bytes) -> None:
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        default_storage.save(file_path, ContentFile(content))
