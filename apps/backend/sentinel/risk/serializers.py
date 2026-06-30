"""Risk serializers."""

from __future__ import annotations

from rest_framework import serializers

from sentinel.risk.models import Alert, AlertRule, AlertSeverity, AlertStatus


class AlertListSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)

    class Meta:
        model = Alert
        fields = [
            "id", "rule_name", "severity", "status",
            "actor_type", "actor_email", "agent_name",
            "risk_score", "risk_level", "created_at",
        ]
        read_only_fields = fields


class AlertDetailSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source="rule.name", read_only=True)
    rule_id = serializers.UUIDField(source="rule.id", read_only=True)
    acknowledged_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "id", "rule_id", "rule_name", "severity", "status",
            "audit_event_id",
            "actor_id", "actor_type", "actor_email", "agent_name",
            "risk_score", "risk_level", "risk_explanation",
            "acknowledged_by_email", "acknowledged_at",
            "resolved_at", "resolution_note",
            "notifications_sent",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_acknowledged_by_email(self, obj: Alert) -> str | None:
        if obj.acknowledged_by:
            return obj.acknowledged_by.email
        return None


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = [
            "id", "name", "description", "is_active", "is_builtin",
            "severity", "condition", "notification_channels",
            "notification_config", "suppression_window_minutes",
            "trigger_count", "created_at",
        ]
        read_only_fields = ["id", "is_builtin", "trigger_count", "created_at"]

    def validate_condition(self, value: dict) -> dict:
        from sentinel.risk.evaluator import ConditionEvaluationError, evaluate_condition
        from sentinel.audit.models import AuditEvent

        # Test the condition against a dummy event to catch structural errors early
        dummy = AuditEvent()
        dummy.risk_score = 0
        dummy.actor_type = "HUMAN"
        dummy.event_type = "USER_LOGIN"
        dummy.agent_name = ""
        dummy.metadata = {}

        try:
            evaluate_condition(value, dummy)
        except ConditionEvaluationError as e:
            raise serializers.ValidationError(f"Invalid condition: {e}") from e
        except Exception:
            pass  # Other errors are OK at this stage — field access on dummy object

        return value

    def validate_notification_channels(self, value: list) -> list:
        valid = {"email", "slack", "webhook", "pagerduty"}
        invalid = set(value) - valid
        if invalid:
            raise serializers.ValidationError(
                f"Invalid channels: {invalid}. Valid: {valid}"
            )
        return value


class ResolveAlertSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, default="", max_length=1000)


class RiskSummarySerializer(serializers.Serializer):
    """Used only for schema generation."""
    open_alerts = serializers.DictField()
    last_24h = serializers.DictField()
    top_risky_ai_agents = serializers.ListField()
