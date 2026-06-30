"""
Migration 0002 for sentinel_risk — seed built-in alert rules.

Built-in rules cannot be deleted (only deactivated) and are created here
so every fresh deployment has sensible defaults without manual configuration.

Rules seeded:
    1. Critical risk score — any actor
    2. High risk AI agent action
    3. AI agent data volume anomaly (velocity spike signal)
    4. Impossible travel — human user
    5. Off-hours admin action
"""

from django.db import migrations


BUILTIN_RULES = [
    {
        "name": "Critical Risk Score — Any Actor",
        "description": (
            "Fires when any actor (human or AI) receives a risk score >= 75. "
            "This indicates highly anomalous behavior requiring immediate investigation."
        ),
        "severity": "critical",
        "is_builtin": True,
        "is_active": True,
        "condition": {"field": "risk_score", "operator": "gte", "value": 75},
        "notification_channels": ["slack", "email"],
        "suppression_window_minutes": 30,
    },
    {
        "name": "High Risk AI Agent Action",
        "description": (
            "Fires when an AI agent receives a risk score >= 50. "
            "AI agents at this threshold may be experiencing prompt injection, "
            "misconfiguration, or operating outside their intended scope."
        ),
        "severity": "high",
        "is_builtin": True,
        "is_active": True,
        "condition": {
            "operator": "AND",
            "conditions": [
                {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
                {"field": "risk_score", "operator": "gte", "value": 50},
            ],
        },
        "notification_channels": ["slack"],
        "suppression_window_minutes": 60,
    },
    {
        "name": "Impossible Travel — Human User",
        "description": (
            "Fires when a human user appears to authenticate from two geographically "
            "distant IP addresses within a short time window, indicating likely "
            "credential compromise or account sharing."
        ),
        "severity": "high",
        "is_builtin": True,
        "is_active": True,
        "condition": {
            "operator": "AND",
            "conditions": [
                {"field": "actor_type", "operator": "eq", "value": "HUMAN"},
                {"field": "risk_score", "operator": "gte", "value": 70},
            ],
        },
        "notification_channels": ["email"],
        "suppression_window_minutes": 120,
    },
    {
        "name": "Off-Hours Admin Action",
        "description": (
            "Fires when an admin user performs a sensitive action outside business hours. "
            "Moderate severity — unusual but may be legitimate. Investigate promptly."
        ),
        "severity": "medium",
        "is_builtin": True,
        "is_active": True,
        "condition": {
            "operator": "AND",
            "conditions": [
                {"field": "actor_role", "operator": "eq", "value": "ADMIN"},
                {"field": "risk_score", "operator": "gte", "value": 30},
                {"field": "event_type", "operator": "in", "value": [
                    "ADMIN_ACTION", "USER_ROLE_CHANGED",
                    "USER_DEACTIVATED", "PERMISSION_CHANGED",
                ]},
            ],
        },
        "notification_channels": ["email"],
        "suppression_window_minutes": 480,
    },
    {
        "name": "AI Agent Accessing New Resource Type",
        "description": (
            "Fires when an AI agent accesses a resource type it has never "
            "touched before. Indicates possible scope creep, prompt injection, "
            "or misconfigured agent permissions."
        ),
        "severity": "high",
        "is_builtin": True,
        "is_active": True,
        "condition": {
            "operator": "AND",
            "conditions": [
                {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
                {"field": "risk_score", "operator": "gte", "value": 55},
            ],
        },
        "notification_channels": ["slack", "email"],
        "suppression_window_minutes": 60,
    },
]


def seed_builtin_rules(apps: object, schema_editor: object) -> None:
    AlertRule = apps.get_model("sentinel_risk", "AlertRule")
    for rule_data in BUILTIN_RULES:
        AlertRule.objects.get_or_create(
            name=rule_data["name"],
            defaults=rule_data,
        )


def remove_builtin_rules(apps: object, schema_editor: object) -> None:
    AlertRule = apps.get_model("sentinel_risk", "AlertRule")
    AlertRule.objects.filter(is_builtin=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("sentinel_risk", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_builtin_rules, remove_builtin_rules),
    ]
