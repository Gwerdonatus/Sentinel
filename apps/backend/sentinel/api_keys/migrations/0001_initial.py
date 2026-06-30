"""Initial migration for sentinel_api_keys."""

import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("sentinel_auth", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="APIKey",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("name", models.CharField(max_length=128)),
                ("actor_type", models.CharField(
                    choices=[("HUMAN_API", "Human Developer API Access"), ("SERVICE", "Backend Service"), ("AI_AGENT", "AI Agent")],
                    db_index=True, default="SERVICE", max_length=20,
                )),
                ("environment", models.CharField(
                    choices=[("live", "Production"), ("test", "Test / Development")],
                    db_index=True, default="live", max_length=10,
                )),
                ("key_prefix", models.CharField(db_index=True, max_length=16, unique=True)),
                ("key_hash", models.CharField(max_length=64)),
                ("scopes", models.JSONField(default=list)),
                ("agent_name", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("agent_version", models.CharField(blank=True, default="", max_length=64)),
                ("agent_description", models.TextField(blank=True, default="")),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("total_uses", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("rotation_grace_until", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_api_keys",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("rotated_from", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rotated_to",
                    to="sentinel_api_keys.apikey",
                )),
            ],
            options={"db_table": "api_keys", "ordering": ["-created_at"], "verbose_name": "API Key"},
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["key_prefix"], name="idx_api_key_prefix"),
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["actor_type", "created_at"], name="idx_api_key_actor_type"),
        ),
        migrations.AddIndex(
            model_name="apikey",
            index=models.Index(fields=["agent_name"], name="idx_api_key_agent_name"),
        ),
    ]
