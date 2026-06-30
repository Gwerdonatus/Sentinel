"""Initial migration for sentinel_risk — AlertRule and Alert tables."""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("sentinel_auth", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertRule",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("is_builtin", models.BooleanField(default=False)),
                ("severity", models.CharField(
                    choices=[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")],
                    db_index=True, default="high", max_length=10,
                )),
                ("condition", models.JSONField()),
                ("notification_channels", models.JSONField(default=list)),
                ("notification_config", models.JSONField(default=dict)),
                ("suppression_window_minutes", models.PositiveIntegerField(default=60)),
                ("trigger_count", models.PositiveIntegerField(default=0)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_alert_rules",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "alert_rules", "ordering": ["-created_at"], "verbose_name": "Alert Rule"},
        ),
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("audit_event_id", models.UUIDField(db_index=True)),
                ("severity", models.CharField(
                    choices=[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")],
                    db_index=True, max_length=10,
                )),
                ("status", models.CharField(
                    choices=[("open","Open"),("acknowledged","Acknowledged"),("resolved","Resolved"),("suppressed","Suppressed (duplicate)")],
                    db_index=True, default="open", max_length=20,
                )),
                ("actor_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("actor_type", models.CharField(blank=True, default="", max_length=20)),
                ("actor_email", models.EmailField(blank=True, default="")),
                ("agent_name", models.CharField(blank=True, default="", max_length=128)),
                ("risk_score", models.SmallIntegerField(blank=True, null=True)),
                ("risk_level", models.CharField(blank=True, default="", max_length=10)),
                ("risk_explanation", models.TextField(blank=True, default="")),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("resolution_note", models.TextField(blank=True, default="")),
                ("notifications_sent", models.JSONField(default=list)),
                ("rule", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="alerts",
                    to="sentinel_risk.alertrule",
                )),
                ("acknowledged_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="acknowledged_alerts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "alerts", "ordering": ["-created_at"], "verbose_name": "Alert"},
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["status","severity","created_at"], name="idx_alert_status_sev"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["actor_id","created_at"], name="idx_alert_actor"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["agent_name","created_at"], name="idx_alert_agent"),
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(fields=["rule","actor_id","created_at"], name="idx_alert_rule_actor"),
        ),
    ]
