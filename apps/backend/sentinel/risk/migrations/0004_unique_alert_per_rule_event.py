from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sentinel_risk", "0003_add_tenant_id")]

    operations = [
        migrations.AddConstraint(
            model_name="alert",
            constraint=models.UniqueConstraint(
                fields=("rule", "audit_event_id"),
                name="uniq_alert_rule_event",
            ),
        )
    ]
