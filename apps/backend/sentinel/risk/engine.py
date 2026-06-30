"""
Risk Scoring Engine.

Runs all applicable risk signals against an audit event and produces
a composite risk score (0-100) with full signal breakdown.

SCORING ALGORITHM:
    1. Run all applicable signals for the actor type
    2. Take the maximum signal score (not average — one strong signal is enough)
    3. Add partial contributions from other fired signals (10% each, max 15 points)
    4. Clamp to 0-100

    This means: one critical signal (85) + two moderate signals (40, 40) = 85 + 8 = 93.
    The dominant signal drives the score; secondary signals amplify it.

RISK LEVELS:
    0-24:   LOW      — routine, expected behavior
    25-49:  MEDIUM   — unusual but likely benign, monitor
    50-74:  HIGH     — anomalous, investigate promptly
    75-100: CRITICAL — likely malicious or severely misconfigured, alert immediately
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from sentinel.risk.signals import (
    SignalResult,
    score_ai_data_volume,
    score_ai_new_resource_type,
    score_impossible_travel,
    score_off_hours_admin,
    score_velocity_spike,
)

if TYPE_CHECKING:
    from sentinel.audit.models import AuditEvent

logger = structlog.get_logger(__name__)


class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @staticmethod
    def from_score(score: int) -> str:
        if score < 25:
            return RiskLevel.LOW
        if score < 50:
            return RiskLevel.MEDIUM
        if score < 75:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL


@dataclass
class RiskScore:
    """Result of the composite risk scoring pipeline."""
    score: int                          # 0-100
    level: str                          # low | medium | high | critical
    signals: list[SignalResult] = field(default_factory=list)
    fired_signals: list[str] = field(default_factory=list)
    primary_signal: str = ""
    explanation: str = ""

    @property
    def is_elevated(self) -> bool:
        return self.score >= 25

    @property
    def requires_alert(self) -> bool:
        return self.score >= 50


# Signal registry — actor type → applicable signals
_HUMAN_SIGNALS = [
    score_impossible_travel,
    score_velocity_spike,
    score_off_hours_admin,
]

_AI_SIGNALS = [
    score_ai_data_volume,
    score_ai_new_resource_type,
    score_velocity_spike,      # Also applies to AI — volume over time
]

_SERVICE_SIGNALS = [
    score_velocity_spike,
]


class RiskEngine:
    """
    Composite risk scoring engine.

    Stateless — can be instantiated per request or as a singleton.
    All state comes from the database via signal functions.
    """

    def score(self, event: "AuditEvent") -> RiskScore:
        """
        Score an audit event for risk.

        Runs applicable signals, computes composite score, returns RiskScore.
        Never raises — returns score=0 on any unexpected error.
        """
        try:
            return self._score(event)
        except Exception as exc:
            logger.error(
                "risk_engine_error",
                event_id=str(event.id),
                event_type=event.event_type,
                error=str(exc),
                exc_info=True,
            )
            return RiskScore(
                score=0,
                level=RiskLevel.LOW,
                explanation="Risk scoring failed — defaulting to 0.",
            )

    def _score(self, event: "AuditEvent") -> RiskScore:
        actor_type = getattr(event, "actor_type", "HUMAN")

        if actor_type == "AI_AGENT":
            signal_fns = _AI_SIGNALS
        elif actor_type == "SERVICE":
            signal_fns = _SERVICE_SIGNALS
        else:
            signal_fns = _HUMAN_SIGNALS

        results: list[SignalResult] = []
        for fn in signal_fns:
            result = fn(event)
            results.append(result)

        fired = [r for r in results if r.fired]

        if not fired:
            return RiskScore(
                score=0,
                level=RiskLevel.LOW,
                signals=results,
                fired_signals=[],
                explanation="No risk signals fired.",
            )

        # Dominant signal drives the score
        primary = max(fired, key=lambda r: r.score)
        composite = primary.score

        # Secondary signals contribute up to 15 additional points
        secondary_fired = [r for r in fired if r is not primary]
        secondary_boost = min(15, len(secondary_fired) * 5)
        composite = min(100, composite + secondary_boost)

        level = RiskLevel.from_score(composite)

        explanation_parts = [f"[{r.signal_name}] {r.reason}" for r in fired]
        explanation = " | ".join(explanation_parts)

        logger.info(
            "risk_score_computed",
            event_id=str(event.id),
            event_type=event.event_type,
            actor_type=actor_type,
            agent_name=getattr(event, "agent_name", "") or None,
            score=composite,
            level=level,
            fired_signals=[r.signal_name for r in fired],
        )

        return RiskScore(
            score=composite,
            level=level,
            signals=results,
            fired_signals=[r.signal_name for r in fired],
            primary_signal=primary.signal_name,
            explanation=explanation,
        )
