"""
Migration: Add tenant_id to all multi-tenant models.

This is a non-breaking additive migration. All existing rows get
tenant_id=NULL which means they belong to no specific tenant
(platform-level records). A data migration to assign them to a
default tenant should be run as a separate step in deployments
that are upgrading from single-tenant to multi-tenant mode.

NULL tenant_id = accessible to superusers only (platform-level).
UUID tenant_id = scoped to that specific tenant.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_audit", "0002_add_actor_type_and_risk_score"),
        ("sentinel_risk", "0002_seed_builtin_rules"),
        ("sentinel_api_keys", "0001_initial"),
        ("sentinel_tenants", "0001_initial"),
    ]

    operations = [
        # AuditEvent
        migrations.AddField(
            model_name="auditevent",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True,
                                   help_text="Owning tenant. Null = platform-level."),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["tenant_id", "created_at"], name="idx_audit_tenant_time"),
        ),

        # Alert
        migrations.AddField(
            model_name="alert",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),

        # AlertRule
        migrations.AddField(
            model_name="alertrule",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),

        # APIKey
        migrations.AddField(
            model_name="apikey",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
