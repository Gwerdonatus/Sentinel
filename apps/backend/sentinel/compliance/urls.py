from django.urls import path

from sentinel.compliance.views import (
    ComplianceReportDetailView,
    ComplianceReportDownloadView,
    ComplianceReportListView,
)

urlpatterns = [
    path("reports/", ComplianceReportListView.as_view(), name="compliance-report-list"),
    path("reports/<str:report_id>/", ComplianceReportDetailView.as_view(), name="compliance-report-detail"),
    path("reports/<str:report_id>/download/", ComplianceReportDownloadView.as_view(), name="compliance-report-download"),
]
