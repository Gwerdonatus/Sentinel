"""Audit Event Serializers."""

from __future__ import annotations

from rest_framework import serializers

from sentinel.audit.models import ActorType, AuditEvent, AuditEventType


class AuditEventSerializer(serializers.ModelSerializer):
    """Serialize audit events for API responses."""

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "tenant_id",
            "event_type",
            "actor_id",
            "actor_type",
            "actor_email",
            "actor_role",
            "actor_ip",
            "agent_name",
            "resource_type",
            "resource_id",
            "metadata",
            "request_id",
            "signature",
            "signature_version",
            "risk_score",
            "created_at",
        ]
        read_only_fields = fields


class AuditEventFilterSerializer(serializers.Serializer):
    """Query parameter validation for audit event list endpoint."""

    actor_id = serializers.UUIDField(required=False)
    actor_type = serializers.ChoiceField(choices=ActorType.choices, required=False)
    agent_name = serializers.CharField(max_length=128, required=False)
    event_type = serializers.ChoiceField(
        choices=AuditEventType.choices,
        required=False,
    )
    resource_type = serializers.CharField(max_length=64, required=False)
    resource_id = serializers.CharField(max_length=128, required=False)
    request_id = serializers.CharField(max_length=64, required=False)
    from_dt = serializers.DateTimeField(required=False)
    to_dt = serializers.DateTimeField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        from_dt = attrs.get("from_dt")
        to_dt = attrs.get("to_dt")
        if from_dt and to_dt and from_dt > to_dt:
            raise serializers.ValidationError({"to_dt": "to_dt must be after from_dt."})
        return attrs


class AuditEventVerifySerializer(serializers.Serializer):
    """Response for signature verification endpoint."""

    event_id = serializers.UUIDField()
    valid = serializers.BooleanField()
    message = serializers.CharField()
