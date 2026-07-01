"""Initial migration for sentinel_compliance."""

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
            name="ComplianceReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("report_type", models.CharField(
                    choices=[("pci_dss","PCI-DSS Evidence"),("soc2","SOC 2 Evidence"),("custom","Custom Export")],
                    db_index=True, max_length=20,
                )),
                ("report_format", models.CharField(
                    choices=[("pdf","PDF"),("csv","CSV"),("json","JSON")],
                    default="pdf", max_length=10,
                )),
                ("status", models.CharField(
                    choices=[("pending","Pending"),("generating","Generating"),("ready","Ready"),("failed","Failed"),("expired","Expired")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("from_dt", models.DateTimeField()),
                ("to_dt", models.DateTimeField()),
                ("filters", models.JSONField(default=dict)),
                ("file_path", models.CharField(blank=True, default="", max_length=512)),
                ("file_size_bytes", models.PositiveIntegerField(blank=True, null=True)),
                ("summary", models.JSONField(default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("generated_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("requested_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="compliance_reports",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "compliance_reports", "ordering": ["-created_at"], "verbose_name": "Compliance Report"},
        ),
    ]
