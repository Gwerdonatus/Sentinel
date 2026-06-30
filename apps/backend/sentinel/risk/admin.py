from django.contrib import admin

from sentinel.risk.models import Alert, AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "severity", "is_active", "is_builtin", "trigger_count", "created_at"]
    list_filter = ["severity", "is_active", "is_builtin"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "trigger_count", "created_at", "updated_at"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = [
        "created_at", "rule", "severity", "status",
        "actor_type", "agent_name", "actor_email", "risk_score",
    ]
    list_filter = ["status", "severity", "actor_type"]
    search_fields = ["agent_name", "actor_email", "audit_event_id"]
    readonly_fields = [f.name for f in Alert._meta.get_fields()]

    def has_add_permission(self, request: object) -> bool:
        return False
