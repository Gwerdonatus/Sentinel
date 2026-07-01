"""Compliance Report Generation Task."""

from __future__ import annotations

import structlog
from celery import shared_task

logger = structlog.get_logger(__name__)


@shared_task(
    name="sentinel.compliance.generate_report",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    time_limit=600,  # 10 minutes hard limit — large reports take time
)
def generate_report_task(self: object, report_id: str) -> None:
    """Generate a compliance report asynchronously."""
    from sentinel.compliance.services import ComplianceReportService

    try:
        ComplianceReportService().generate(report_id)
    except Exception as exc:
        logger.error("compliance_report_task_failed", report_id=report_id, error=str(exc))
        raise self.retry(exc=exc)  # type: ignore[union-attr]
