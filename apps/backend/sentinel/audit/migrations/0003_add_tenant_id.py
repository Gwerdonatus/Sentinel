from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_audit", "0002_add_actor_type_and_risk_score"),
        ("sentinel_tenants", "0002_add_tenant_id_to_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="tenant_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text="Owning tenant. Null = platform-level.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["tenant_id", "created_at"], name="idx_audit_tenant_time"),
        ),
    ]
