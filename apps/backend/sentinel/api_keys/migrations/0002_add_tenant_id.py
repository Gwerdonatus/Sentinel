from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_api_keys", "0001_initial"),
        ("sentinel_tenants", "0002_add_tenant_id_to_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="apikey",
            name="tenant_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
