"""Initial migration for sentinel_tenants."""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("plan", models.CharField(
                    choices=[("starter","Starter"),("growth","Growth"),("enterprise","Enterprise")],
                    default="starter", max_length=20,
                )),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("kafka_topic_prefix", models.CharField(blank=True, max_length=128)),
                ("max_events_per_day", models.PositiveIntegerField(default=100000)),
                ("max_api_keys", models.PositiveIntegerField(default=20)),
                ("max_alert_rules", models.PositiveIntegerField(default=50)),
                ("owner_email", models.EmailField()),
            ],
            options={"db_table": "tenants", "ordering": ["name"], "verbose_name": "Tenant"},
        ),
    ]
