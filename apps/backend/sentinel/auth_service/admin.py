from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from sentinel.auth_service.models import SentinelUser


@admin.register(SentinelUser)
class SentinelUserAdmin(UserAdmin):
    model = SentinelUser
    list_display = ["email", "full_name", "role", "is_active", "last_login", "created_at"]
    list_filter = ["role", "is_active", "must_change_password"]
    search_fields = ["email", "full_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at", "last_login", "last_login_ip", "failed_login_count"]

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Profile", {"fields": ("full_name",)}),
        ("Authorization", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Security", {"fields": ("must_change_password", "last_login_ip", "failed_login_count", "password_changed_at")}),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "password1", "password2"),
        }),
    )
