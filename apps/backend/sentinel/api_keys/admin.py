from django.contrib import admin

from sentinel.api_keys.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = [
        "name", "actor_type", "agent_name", "environment",
        "is_active", "total_uses", "last_used_at", "created_at",
    ]
    list_filter = ["actor_type", "environment"]
    search_fields = ["name", "agent_name", "key_prefix"]
    readonly_fields = [
        "id", "key_prefix", "key_hash", "total_uses",
        "last_used_at", "last_used_ip", "created_at", "updated_at",
    ]

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False  # Keys are immutable after creation — only revocable
