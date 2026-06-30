"""
Risk Scoring Signals.

Each function in this module is an independent risk signal.
It receives an AuditEvent and historical context, returns a score 0-100.

The composite scorer in engine.py runs all applicable signals,
weights them, and returns a final composite score.

DESIGN PRINCIPLES:
- Each signal is independently testable with no side effects
- Signals never raise — they return 0 on any error (fail open, not closed)
- Human signals and AI agent signals are separated for clarity
- All signals receive the same interface: (event, context) -> int

HUMAN ACTOR SIGNALS:
- impossible_travel: same actor, two distant IPs in short time window
- velocity_spike: actor performing far more actions than their baseline
- new_device_high_value: first time from this IP + high-value action
- off_hours_admin: admin action outside normal business hours

AI AGENT SIGNALS:
- ai_data_volume: AI agent accessing far more records than baseline
- ai_scope_creep: AI agent accessing resource types outside its normal pattern
- ai_velocity: AI agent making requests at anomalous rate
- ai_new_resource_type: AI agent accessing a resource type it has never touched

COMPOSITE WEIGHTS (in engine.py):
    Human signals weighted toward behavioral anomaly (travel, velocity)
    AI signals weighted toward volume and scope (data exfiltration patterns)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import structlog
from django.utils import timezone

if TYPE_CHECKING:
    from sentinel.audit.models import AuditEvent

logger = structlog.get_logger(__name__)


@dataclass
class SignalResult:
    """Result of a single risk signal evaluation."""
    signal_name: str
    score: int          # 0-100
    fired: bool         # True if this signal contributed meaningfully
    reason: str = ""    # Human-readable explanation if fired


def score_impossible_travel(
    event: "AuditEvent",
    lookback_minutes: int = 30,
) -> SignalResult:
    """
    Detect impossible travel: same actor, two distant IPs within a short window.

    Compares the current event's IP against recent events from the same actor.
    If the geographic distance implies faster-than-possible travel, score high.

    Implementation note: Full geolocation lookup is expensive and requires an
    external service. This implementation uses IP subnet similarity as a fast
    proxy — same /16 subnet = probably same region. Different /16 = possible travel.
    Phase 4 integrates a proper geo-IP service.
    """
    from sentinel.audit.models import AuditEvent as AuditEventModel

    if not event.actor_id or not event.actor_ip:
        return SignalResult("impossible_travel", 0, False)

    try:
        cutoff = timezone.now() - timedelta(minutes=lookback_minutes)
        recent = (
            AuditEventModel.objects.filter(
                actor_id=event.actor_id,
                created_at__gte=cutoff,
                actor_ip__isnull=False,
            )
            .exclude(id=event.id)
            .exclude(actor_ip=event.actor_ip)
            .values_list("actor_ip", flat=True)
            .distinct()[:10]
        )

        current_subnet = ".".join(event.actor_ip.split(".")[:2])

        for recent_ip in recent:
            recent_subnet = ".".join(str(recent_ip).split(".")[:2])
            if current_subnet != recent_subnet:
                return SignalResult(
                    "impossible_travel",
                    score=85,
                    fired=True,
                    reason=(
                        f"Actor seen at {event.actor_ip} within {lookback_minutes}m "
                        f"of different subnet {recent_ip}"
                    ),
                )
    except Exception as exc:
        logger.warning("signal_error", signal="impossible_travel", error=str(exc))

    return SignalResult("impossible_travel", 0, False)


def score_velocity_spike(
    event: "AuditEvent",
    window_minutes: int = 60,
    spike_multiplier: float = 5.0,
    baseline_days: int = 7,
) -> SignalResult:
    """
    Detect velocity spikes: actor performing far more actions than their baseline.

    Compares the current hour's event count to the actor's 7-day hourly baseline.
    A 5x spike scores 70. A 10x spike scores 90.
    """
    from sentinel.audit.models import AuditEvent as AuditEventModel
    from django.db.models import Count

    if not event.actor_id:
        return SignalResult("velocity_spike", 0, False)

    try:
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)
        baseline_start = now - timedelta(days=baseline_days)

        current_count = AuditEventModel.objects.filter(
            actor_id=event.actor_id,
            created_at__gte=window_start,
        ).count()

        # Hourly average over the baseline period
        baseline_total = AuditEventModel.objects.filter(
            actor_id=event.actor_id,
            created_at__gte=baseline_start,
            created_at__lt=window_start,
        ).count()

        baseline_hours = (baseline_days * 24) - (window_minutes / 60)
        hourly_baseline = baseline_total / max(baseline_hours, 1)

        if hourly_baseline < 1:
            # Not enough history for a meaningful baseline
            return SignalResult("velocity_spike", 0, False)

        ratio = current_count / hourly_baseline

        if ratio >= spike_multiplier:
            # Log scale scoring: 5x = 70, 10x = 85, 20x+ = 95
            score = min(95, int(70 + math.log2(ratio / spike_multiplier) * 10))
            return SignalResult(
                "velocity_spike",
                score=score,
                fired=True,
                reason=f"{current_count} events in {window_minutes}m vs {hourly_baseline:.1f}/hr baseline ({ratio:.1f}x spike)",
            )
    except Exception as exc:
        logger.warning("signal_error", signal="velocity_spike", error=str(exc))

    return SignalResult("velocity_spike", 0, False)


def score_off_hours_admin(
    event: "AuditEvent",
    business_start_hour: int = 7,
    business_end_hour: int = 20,
) -> SignalResult:
    """
    Score admin actions outside business hours.

    An admin performing sensitive actions at 3am is unusual.
    Score is moderate (40) — unusual but not necessarily malicious.
    Combined with other signals it contributes to a high composite score.
    """
    SENSITIVE_EVENT_TYPES = {
        "ADMIN_ACTION", "USER_ROLE_CHANGED", "USER_DEACTIVATED",
        "PERMISSION_CHANGED", "API_KEY_REVOKED",
    }

    if event.event_type not in SENSITIVE_EVENT_TYPES:
        return SignalResult("off_hours_admin", 0, False)

    if event.actor_role not in ("ADMIN",):
        return SignalResult("off_hours_admin", 0, False)

    try:
        hour = event.created_at.hour
        if not (business_start_hour <= hour < business_end_hour):
            return SignalResult(
                "off_hours_admin",
                score=40,
                fired=True,
                reason=f"Admin action '{event.event_type}' at hour {hour} UTC (outside {business_start_hour}-{business_end_hour})",
            )
    except Exception as exc:
        logger.warning("signal_error", signal="off_hours_admin", error=str(exc))

    return SignalResult("off_hours_admin", 0, False)


def score_ai_data_volume(
    event: "AuditEvent",
    window_minutes: int = 60,
    volume_threshold_multiplier: float = 10.0,
    baseline_days: int = 7,
) -> SignalResult:
    """
    Detect AI agents accessing anomalously large amounts of data.

    This is the primary AI-specific exfiltration signal.
    An AI agent that suddenly accesses 10x its normal data volume
    is a high-priority alert — possible prompt injection or misconfiguration.
    """
    from sentinel.audit.models import AuditEvent as AuditEventModel

    if event.actor_type != "AI_AGENT" or not event.agent_name:
        return SignalResult("ai_data_volume", 0, False)

    DATA_ACCESS_TYPES = {"TRANSFER_INITIATED", "TRANSFER_APPROVED", "ADMIN_ACTION"}

    if event.event_type not in DATA_ACCESS_TYPES:
        return SignalResult("ai_data_volume", 0, False)

    try:
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)
        baseline_start = now - timedelta(days=baseline_days)

        current_count = AuditEventModel.objects.filter(
            agent_name=event.agent_name,
            actor_type="AI_AGENT",
            event_type__in=DATA_ACCESS_TYPES,
            created_at__gte=window_start,
        ).count()

        baseline_total = AuditEventModel.objects.filter(
            agent_name=event.agent_name,
            actor_type="AI_AGENT",
            event_type__in=DATA_ACCESS_TYPES,
            created_at__gte=baseline_start,
            created_at__lt=window_start,
        ).count()

        baseline_hours = (baseline_days * 24) - (window_minutes / 60)
        hourly_baseline = baseline_total / max(baseline_hours, 1)

        if hourly_baseline < 1:
            return SignalResult("ai_data_volume", 0, False)

        ratio = current_count / hourly_baseline

        if ratio >= volume_threshold_multiplier:
            score = min(95, int(80 + math.log2(ratio / volume_threshold_multiplier) * 5))
            return SignalResult(
                "ai_data_volume",
                score=score,
                fired=True,
                reason=(
                    f"AI agent '{event.agent_name}' accessed {current_count} records "
                    f"in {window_minutes}m vs {hourly_baseline:.1f}/hr baseline "
                    f"({ratio:.1f}x — possible data exfiltration)"
                ),
            )
    except Exception as exc:
        logger.warning("signal_error", signal="ai_data_volume", error=str(exc))

    return SignalResult("ai_data_volume", 0, False)


def score_ai_new_resource_type(
    event: "AuditEvent",
    lookback_days: int = 30,
) -> SignalResult:
    """
    Detect AI agents accessing resource types they have never touched before.

    An AI support agent that suddenly starts accessing 'transfer' resources
    when it has only ever touched 'user' resources is a scope violation signal.
    """
    from sentinel.audit.models import AuditEvent as AuditEventModel

    if event.actor_type != "AI_AGENT" or not event.agent_name or not event.resource_type:
        return SignalResult("ai_new_resource_type", 0, False)

    try:
        cutoff = timezone.now() - timedelta(days=lookback_days)
        known_types = set(
            AuditEventModel.objects.filter(
                agent_name=event.agent_name,
                actor_type="AI_AGENT",
                created_at__gte=cutoff,
            )
            .exclude(id=event.id)
            .exclude(resource_type="")
            .values_list("resource_type", flat=True)
            .distinct()
        )

        if known_types and event.resource_type not in known_types:
            return SignalResult(
                "ai_new_resource_type",
                score=60,
                fired=True,
                reason=(
                    f"AI agent '{event.agent_name}' accessed new resource type "
                    f"'{event.resource_type}'. Known types: {', '.join(known_types)}"
                ),
            )
    except Exception as exc:
        logger.warning("signal_error", signal="ai_new_resource_type", error=str(exc))

    return SignalResult("ai_new_resource_type", 0, False)
