"""
Initial migration for sentinel_auth — custom SentinelUser model.
"""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="SentinelUser",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(
                    default=False,
                    verbose_name="superuser status",
                    help_text="Designates that this user has all permissions without explicitly assigning them.",
                )),
                ("id", models.UUIDField(
                    primary_key=True, default=uuid.uuid4, editable=False, serialize=False,
                )),
                ("email", models.EmailField(
                    max_length=254, unique=True, db_index=True,
                    help_text="Primary identifier and login credential.",
                )),
                ("full_name", models.CharField(
                    max_length=255, blank=True,
                    help_text="Display name for audit logs and UI.",
                )),
                ("role", models.CharField(
                    max_length=20, db_index=True, default="VIEWER",
                    choices=[
                        ("ADMIN", "Administrator"),
                        ("AUDITOR", "Auditor"),
                        ("ANALYST", "Analyst"),
                        ("VIEWER", "Viewer"),
                    ],
                    help_text="RBAC role governing platform access.",
                )),
                ("is_staff", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True, db_index=True)),
                ("last_login_ip", models.GenericIPAddressField(null=True, blank=True)),
                ("failed_login_count", models.PositiveSmallIntegerField(default=0)),
                ("password_changed_at", models.DateTimeField(null=True, blank=True)),
                ("must_change_password", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("groups", models.ManyToManyField(
                    blank=True, to="auth.group", verbose_name="groups",
                    related_name="sentinel_user_set", related_query_name="sentinel_user",
                    help_text="The groups this user belongs to.",
                )),
                ("user_permissions", models.ManyToManyField(
                    blank=True, to="auth.permission", verbose_name="user permissions",
                    related_name="sentinel_user_set", related_query_name="sentinel_user",
                    help_text="Specific permissions for this user.",
                )),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "db_table": "sentinel_users",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sentineluser",
            index=models.Index(fields=["email", "is_active"], name="idx_user_email_active"),
        ),
        migrations.AddIndex(
            model_name="sentineluser",
            index=models.Index(fields=["role", "is_active"], name="idx_user_role_active"),
        ),
    ]
