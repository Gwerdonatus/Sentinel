"""
Migration 0002 for sentinel_audit.

Adds actor identity fields to support the AI actor model:

  actor_type  — HUMAN | SERVICE | AI_AGENT
  agent_name  — name of the AI agent or service (e.g. "support-bot-v2")
  risk_score  — composite risk score computed by Phase 3 risk engine (0-100)

All existing rows default to actor_type=HUMAN, agent_name='', risk_score=None.
This migration is non-breaking and additive.

WHY ON THE AUDIT TABLE:
  Actor type belongs on the event itself, not on a related model.
  Investigation queries must be fast. "Show me all AI agent events in the last hour"
  should be a single indexed column scan — not a join through actor identity tables.
  Denormalization here is intentional and correct.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="actor_type",
            field=models.CharField(
                max_length=20,
                default="HUMAN",
                db_index=True,
                choices=[
                    ("HUMAN", "Human User"),
                    ("SERVICE", "Backend Service"),
                    ("AI_AGENT", "AI Agent"),
                ],
                help_text=(
                    "Type of actor that performed this action. "
                    "HUMAN: authenticated user. "
                    "SERVICE: backend service or automated pipeline. "
                    "AI_AGENT: AI model or agent (LLM, support bot, MCP server, etc.)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="agent_name",
            field=models.CharField(
                max_length=128,
                blank=True,
                default="",
                db_index=True,
                help_text=(
                    "Name of the AI agent or service. "
                    "Populated when actor_type is AI_AGENT or SERVICE. "
                    "Examples: 'support-bot-v2', 'fraud-detector', 'gpt-4-reconciler'."
                ),
            ),
        ),
        migrations.AddField(
            model_name="auditevent",
            name="risk_score",
            field=models.SmallIntegerField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Composite risk score (0-100) computed by the risk engine. "
                    "Null until the risk engine processes this event. "
                    "0-24: low, 25-49: medium, 50-74: high, 75-100: critical."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["actor_type", "created_at"],
                name="idx_audit_actor_type_time",
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["agent_name", "created_at"],
                name="idx_audit_agent_name_time",
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["risk_score", "created_at"],
                name="idx_audit_risk_score_time",
            ),
        ),
    ]
