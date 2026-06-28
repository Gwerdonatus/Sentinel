"""
Initial migration for sentinel_audit.

Creates the audit_events table — the immutable ledger at the heart of Sentinel.

Schema notes:
- UUID primary key (non-enumerable, distributed-safe)
- No updated_at field — this table is append-only by design
- created_at is the candidate partition key (range by month, Phase 5)
- actor_id is nullable (failed logins have no authenticated actor)
- Comprehensive indexes for the most common query patterns
"""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        # Audit depends on auth being set up so we can reference users
        ("sentinel_auth", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("actor_id", models.UUIDField(
                    blank=True,
                    db_index=True,
                    help_text="UUID of the authenticated user who performed this action.",
                    null=True,
                )),
                ("actor_email", models.EmailField(
                    blank=True,
                    default="",
                    help_text="Email snapshot at time of event.",
                    max_length=254,
                )),
                ("actor_role", models.CharField(
                    blank=True,
                    default="",
                    help_text="Role snapshot at time of event.",
                    max_length=20,
                )),
                ("actor_ip", models.GenericIPAddressField(
                    blank=True,
                    null=True,
                    help_text="IP address of the actor at time of event.",
                )),
                ("event_type", models.CharField(
                    choices=[
                        ("USER_LOGIN", "User Login"),
                        ("USER_LOGOUT", "User Logout"),
                        ("USER_LOGIN_FAILED", "User Login Failed"),
                        ("PASSWORD_RESET_REQUESTED", "Password Reset Requested"),
                        ("PASSWORD_RESET_COMPLETED", "Password Reset Completed"),
                        ("PASSWORD_CHANGED", "Password Changed"),
                        ("USER_CREATED", "User Created"),
                        ("USER_DEACTIVATED", "User Deactivated"),
                        ("USER_ROLE_CHANGED", "User Role Changed"),
                        ("API_KEY_CREATED", "API Key Created"),
                        ("API_KEY_ROTATED", "API Key Rotated"),
                        ("API_KEY_REVOKED", "API Key Revoked"),
                        ("TRANSFER_INITIATED", "Transfer Initiated"),
                        ("TRANSFER_APPROVED", "Transfer Approved"),
                        ("TRANSFER_REJECTED", "Transfer Rejected"),
                        ("ADMIN_ACTION", "Admin Action"),
                        ("PERMISSION_CHANGED", "Permission Changed"),
                        ("WEBHOOK_DELIVERED", "Webhook Delivered"),
                        ("WEBHOOK_FAILED", "Webhook Failed"),
                    ],
                    db_index=True,
                    max_length=64,
                )),
                ("resource_type", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("resource_id", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("metadata", models.JSONField(default=dict)),
                ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("signature", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "verbose_name": "Audit Event",
                "verbose_name_plural": "Audit Events",
                "db_table": "audit_events",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["actor_id", "created_at"], name="idx_audit_actor_time"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["event_type", "created_at"], name="idx_audit_type_time"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["resource_type", "resource_id"], name="idx_audit_resource"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["request_id"], name="idx_audit_request_id"),
        ),
    ]
