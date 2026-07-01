"""Compliance serializers."""

from __future__ import annotations

from rest_framework import serializers

from sentinel.compliance.models import ComplianceReport, ReportFormat, ReportType


class ComplianceReportRequestSerializer(serializers.Serializer):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    report_format = serializers.ChoiceField(choices=ReportFormat.choices, default="pdf")
    from_dt = serializers.DateTimeField()
    to_dt = serializers.DateTimeField()
    filters = serializers.DictField(required=False, default=dict)

    def validate(self, attrs: dict) -> dict:
        if attrs["from_dt"] >= attrs["to_dt"]:
            raise serializers.ValidationError({"to_dt": "to_dt must be after from_dt."})

        span_days = (attrs["to_dt"] - attrs["from_dt"]).days
        if span_days > 366:
            raise serializers.ValidationError(
                {"to_dt": "Report period cannot exceed 366 days."}
            )
        return attrs


class ComplianceReportSerializer(serializers.ModelSerializer):
    requested_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceReport
        fields = [
            "id", "report_type", "report_format", "status",
            "from_dt", "to_dt", "filters", "summary",
            "file_size_bytes", "error_message",
            "requested_by_email", "generated_at", "expires_at", "created_at",
        ]
        read_only_fields = fields

    def get_requested_by_email(self, obj: ComplianceReport) -> str | None:
        return obj.requested_by.email if obj.requested_by else None
