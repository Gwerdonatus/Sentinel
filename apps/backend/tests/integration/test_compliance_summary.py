from datetime import timedelta

import pytest
from django.utils import timezone

from sentinel.audit.models import AuditEvent
from sentinel.compliance.services import ComplianceReportService


@pytest.mark.django_db
def test_summary_groups_ordered_events_without_losing_actor_counts() -> None:
    now = timezone.now()
    actors = ["AI_AGENT", "AI_AGENT", "AI_AGENT", "HUMAN", "HUMAN", "SERVICE"]
    agents = ["alpha", "alpha", "beta", "", "", ""]
    scores = [0, 60, 0, 90, 0, 0]
    for index, (actor, agent, score) in enumerate(zip(actors, agents, scores, strict=True)):
        AuditEvent.objects.create(
            actor_type=actor,
            agent_name=agent,
            event_type="ADMIN_ACTION" if index < 4 else "USER_LOGIN",
            risk_score=score,
            created_at=now + timedelta(seconds=index),
            signature="summary-test-fixture",
        )
    events = AuditEvent.objects.order_by("created_at")
    summary = ComplianceReportService()._build_summary(events)
    assert summary["total_events"] == 6
    assert summary["by_actor_type"] == {"AI_AGENT": 3, "HUMAN": 2, "SERVICE": 1}
    assert sum(summary["by_actor_type"].values()) == summary["total_events"]
    assert summary["ai_agents_involved"] == [
        {"agent_name": "alpha", "event_count": 2},
        {"agent_name": "beta", "event_count": 1},
    ]
    assert summary["high_risk_event_count"] == 2
    assert summary["top_event_types"] == {"ADMIN_ACTION": 4, "USER_LOGIN": 2}
    assert events.query.order_by == ("created_at",)


@pytest.mark.django_db
def test_empty_summary_has_consistent_zero_totals() -> None:
    summary = ComplianceReportService()._build_summary(AuditEvent.objects.none())
    assert summary["total_events"] == 0
    assert summary["by_actor_type"] == {}
    assert summary["ai_agents_involved"] == []
    assert summary["high_risk_event_count"] == 0
    assert summary["top_event_types"] == {}
