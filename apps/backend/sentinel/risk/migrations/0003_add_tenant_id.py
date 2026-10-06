from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_risk", "0002_seed_builtin_rules"),
        ("sentinel_tenants", "0002_add_tenant_id_to_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="alertrule",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
