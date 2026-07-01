from django.contrib import admin

from sentinel.compliance.models import ComplianceReport


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ["report_type", "report_format", "status", "from_dt", "to_dt", "requested_by", "created_at"]
    list_filter = ["report_type", "status", "report_format"]
    readonly_fields = ["id", "summary", "file_path", "file_size_bytes", "created_at", "updated_at"]

    def has_add_permission(self, request: object) -> bool:
        return False
