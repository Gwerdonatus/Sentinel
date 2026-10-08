import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sentinel_audit", "0003_add_tenant_id")]

    operations = [
        migrations.AlterField(
            model_name="auditevent",
            name="created_at",
            field=models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
                help_text="UTC timestamp when this event was recorded. Immutable.",
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="signature_version",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Canonical signing format. Version 2 covers all security-relevant fields.",
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="signature_version",
            field=models.PositiveSmallIntegerField(
                default=2,
                help_text="Canonical signing format. Version 2 covers all security-relevant fields.",
            ),
        ),
        migrations.CreateModel(
            name="AuditOutbox",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                (
                    "next_attempt_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                ("published_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                (
                    "created_at",
                    models.DateTimeField(db_index=True, default=django.utils.timezone.now),
                ),
                (
                    "audit_event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="outbox_entry",
                        to="sentinel_audit.auditevent",
                    ),
                ),
            ],
            options={"db_table": "audit_outbox", "ordering": ["created_at"]},
        ),
        migrations.AddIndex(
            model_name="auditoutbox",
            index=models.Index(
                fields=["published_at", "next_attempt_at"],
                name="idx_outbox_pending",
            ),
        ),
    ]
