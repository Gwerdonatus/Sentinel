"""
Compliance Report Model.

A ComplianceReport record tracks the lifecycle of a requested export:
PENDING -> GENERATING -> READY -> EXPIRED (or FAILED)

Reports are generated asynchronously because evidence packages can span
months of audit data. The dashboard polls report status and downloads
the file once READY.

REPORT TYPES:
    PCI_DSS    — Payment card data access events, formatted for PCI evidence
    SOC2       — General control evidence: auth, access changes, admin actions
    CUSTOM     — User-defined filter set, free-form date range

AI ATTRIBUTION:
    Every report explicitly separates HUMAN, SERVICE, and AI_AGENT actors
    in its summary section. This is the feature that distinguishes a
    Sentinel compliance report from a generic audit export — an auditor
    can see at a glance which actions were taken by named AI agents.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from sentinel.core.models.base import TimestampedModel


class ReportType(models.TextChoices):
    PCI_DSS = "pci_dss", "PCI-DSS Evidence"
    SOC2 = "soc2", "SOC 2 Evidence"
    CUSTOM = "custom", "Custom Export"


class ReportFormat(models.TextChoices):
    PDF = "pdf", "PDF"
    CSV = "csv", "CSV"
    JSON = "json", "JSON"


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    GENERATING = "generating", "Generating"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
    EXPIRED = "expired", "Expired"


class ComplianceReport(TimestampedModel):
    """A requested compliance evidence export."""

    report_type = models.CharField(max_length=20, choices=ReportType.choices, db_index=True)
    report_format = models.CharField(max_length=10, choices=ReportFormat.choices, default=ReportFormat.PDF)
    status = models.CharField(max_length=20, choices=ReportStatus.choices, default=ReportStatus.PENDING, db_index=True)

    # Filter parameters used to generate this report
    from_dt = models.DateTimeField()
    to_dt = models.DateTimeField()
    filters = models.JSONField(
        default=dict,
        help_text="Additional filters: event_type, actor_type, resource_type, agent_name, etc.",
    )

    # Output
    file_path = models.CharField(max_length=512, blank=True, default="")
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)

    # Summary statistics — computed during generation, shown in the report header
    summary = models.JSONField(
        default=dict,
        help_text=(
            "Computed summary: total_events, by actor_type breakdown, "
            "ai_agents_involved list, alert_count, etc."
        ),
    )

    error_message = models.TextField(blank=True, default="")

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_reports",
    )

    generated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Download link expires after this time. File is purged.",
    )

    class Meta:
        db_table = "compliance_reports"
        ordering = ["-created_at"]
        verbose_name = "Compliance Report"
        verbose_name_plural = "Compliance Reports"

    def __str__(self) -> str:
        return f"ComplianceReport({self.report_type}, {self.status}, {self.from_dt.date()}-{self.to_dt.date()})"
