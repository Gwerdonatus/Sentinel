"""API Key serializers."""

from __future__ import annotations

from rest_framework import serializers

from sentinel.api_keys.models import APIKey, ActorType, KeyEnvironment


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    actor_type = serializers.ChoiceField(choices=ActorType.choices)
    scopes = serializers.ListField(child=serializers.CharField(), min_length=1)
    environment = serializers.ChoiceField(choices=KeyEnvironment.choices, default="live")
    agent_name = serializers.CharField(max_length=128, required=False, default="")
    agent_version = serializers.CharField(max_length=64, required=False, default="")
    agent_description = serializers.CharField(required=False, default="")
    expires_in_days = serializers.IntegerField(required=False, min_value=1, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        if attrs.get("actor_type") == ActorType.AI_AGENT and not attrs.get("agent_name"):
            raise serializers.ValidationError(
                {"agent_name": "agent_name is required for AI_AGENT keys."}
            )
        return attrs


class APIKeyResponseSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id", "name", "actor_type", "environment",
            "key_prefix",  # Safe to expose — it's just a lookup prefix
            "scopes", "agent_name", "agent_version", "agent_description",
            "is_active", "is_expired",
            "last_used_at", "last_used_ip", "total_uses",
            "expires_at", "created_by_email", "created_at",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj: APIKey) -> str | None:
        return obj.created_by.email if obj.created_by else None


class APIKeyCreatedResponseSerializer(APIKeyResponseSerializer):
    """Extends response with the one-time key value."""
    key = serializers.CharField(read_only=True, help_text="Full key — shown once, never retrievable.")

    class Meta(APIKeyResponseSerializer.Meta):
        fields = APIKeyResponseSerializer.Meta.fields + ["key"]  # type: ignore[operator]
