from django.contrib import admin

from sentinel.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = [
        "created_at", "event_type", "actor_email",
        "actor_role", "resource_type", "resource_id", "actor_ip",
    ]
    list_filter = ["event_type", "resource_type", "actor_role"]
    search_fields = ["actor_email", "resource_id", "request_id"]
    readonly_fields = [f.name for f in AuditEvent._meta.get_fields()]
    ordering = ["-created_at"]

    def has_add_permission(self, request: object) -> bool:
        return False  # Audit events are only created programmatically

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        return False  # Immutable

    def has_delete_permission(self, request: object, obj: object = None) -> bool:
        return False  # Immutable
