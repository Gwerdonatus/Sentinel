"""
Unit Tests — Risk Engine and Signals.

Tests the scoring pipeline, individual signals, and condition evaluator.
No database required for engine and evaluator tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import uuid

import pytest

from sentinel.risk.engine import RiskEngine, RiskLevel, RiskScore
from sentinel.risk.evaluator import ConditionEvaluationError, evaluate_condition
from sentinel.risk.signals import SignalResult


def make_event(**kwargs: object) -> MagicMock:
    """Build a mock AuditEvent for signal testing."""
    event = MagicMock()
    event.id = kwargs.get("id", uuid.uuid4())
    event.actor_id = kwargs.get("actor_id", uuid.uuid4())
    event.actor_type = kwargs.get("actor_type", "HUMAN")
    event.actor_email = kwargs.get("actor_email", "user@sentinel.io")
    event.actor_role = kwargs.get("actor_role", "VIEWER")
    event.actor_ip = kwargs.get("actor_ip", "1.2.3.4")
    event.agent_name = kwargs.get("agent_name", "")
    event.event_type = kwargs.get("event_type", "USER_LOGIN")
    event.resource_type = kwargs.get("resource_type", "user")
    event.resource_id = kwargs.get("resource_id", "")
    event.risk_score = kwargs.get("risk_score", None)
    event.metadata = kwargs.get("metadata", {})
    event.created_at = kwargs.get("created_at", datetime(2025, 6, 14, 10, 0, 0, tzinfo=timezone.utc))
    return event


class TestRiskLevel:
    def test_score_0_is_low(self) -> None:
        assert RiskLevel.from_score(0) == RiskLevel.LOW

    def test_score_24_is_low(self) -> None:
        assert RiskLevel.from_score(24) == RiskLevel.LOW

    def test_score_25_is_medium(self) -> None:
        assert RiskLevel.from_score(25) == RiskLevel.MEDIUM

    def test_score_49_is_medium(self) -> None:
        assert RiskLevel.from_score(49) == RiskLevel.MEDIUM

    def test_score_50_is_high(self) -> None:
        assert RiskLevel.from_score(50) == RiskLevel.HIGH

    def test_score_74_is_high(self) -> None:
        assert RiskLevel.from_score(74) == RiskLevel.HIGH

    def test_score_75_is_critical(self) -> None:
        assert RiskLevel.from_score(75) == RiskLevel.CRITICAL

    def test_score_100_is_critical(self) -> None:
        assert RiskLevel.from_score(100) == RiskLevel.CRITICAL


class TestRiskScore:
    def test_score_0_is_not_elevated(self) -> None:
        rs = RiskScore(score=0, level=RiskLevel.LOW)
        assert rs.is_elevated is False

    def test_score_25_is_elevated(self) -> None:
        rs = RiskScore(score=25, level=RiskLevel.MEDIUM)
        assert rs.is_elevated is True

    def test_score_49_does_not_require_alert(self) -> None:
        rs = RiskScore(score=49, level=RiskLevel.MEDIUM)
        assert rs.requires_alert is False

    def test_score_50_requires_alert(self) -> None:
        rs = RiskScore(score=50, level=RiskLevel.HIGH)
        assert rs.requires_alert is True


class TestRiskEngineNoSignalsFired:
    def test_returns_zero_score_when_no_signals_fire(self) -> None:
        engine = RiskEngine()
        event = make_event()

        with patch("sentinel.risk.signals.score_impossible_travel") as m_travel, \
             patch("sentinel.risk.signals.score_velocity_spike") as m_velocity, \
             patch("sentinel.risk.signals.score_off_hours_admin") as m_hours:
            m_travel.return_value = SignalResult("impossible_travel", 0, False)
            m_velocity.return_value = SignalResult("velocity_spike", 0, False)
            m_hours.return_value = SignalResult("off_hours_admin", 0, False)

            result = engine.score(event)

        assert result.score == 0
        assert result.level == RiskLevel.LOW
        assert result.fired_signals == []

    def test_never_raises_on_signal_error(self) -> None:
        engine = RiskEngine()
        event = make_event()

        with patch("sentinel.risk.engine._HUMAN_SIGNALS", [lambda e: 1 / 0]):
            result = engine.score(event)

        assert result.score == 0
        assert "failed" in result.explanation


class TestRiskEngineScoring:
    def test_single_signal_score_is_dominant(self) -> None:
        engine = RiskEngine()
        event = make_event()

        with patch("sentinel.risk.engine._HUMAN_SIGNALS", [
            lambda e: SignalResult("sig_a", 80, True, "fired"),
            lambda e: SignalResult("sig_b", 0, False),
        ]):
            result = engine.score(event)

        assert result.score == 80
        assert result.primary_signal == "sig_a"

    def test_secondary_signals_add_boost(self) -> None:
        engine = RiskEngine()
        event = make_event()

        with patch("sentinel.risk.engine._HUMAN_SIGNALS", [
            lambda e: SignalResult("primary", 80, True, "main"),
            lambda e: SignalResult("secondary", 40, True, "boost"),
        ]):
            result = engine.score(event)

        # 80 (primary) + 5 (one secondary) = 85
        assert result.score == 85

    def test_secondary_boost_capped_at_15(self) -> None:
        engine = RiskEngine()
        event = make_event()

        # 4 secondary signals → would be 20 boost, capped at 15
        with patch("sentinel.risk.engine._HUMAN_SIGNALS", [
            lambda e: SignalResult("primary", 70, True, "p"),
            lambda e: SignalResult("s1", 30, True, "s"),
            lambda e: SignalResult("s2", 30, True, "s"),
            lambda e: SignalResult("s3", 30, True, "s"),
            lambda e: SignalResult("s4", 30, True, "s"),
        ]):
            result = engine.score(event)

        assert result.score == min(100, 70 + 15)

    def test_ai_agent_uses_ai_signals(self) -> None:
        engine = RiskEngine()
        event = make_event(actor_type="AI_AGENT", agent_name="support-bot")

        called_signals: list[str] = []

        def mock_ai_signal(e: object) -> SignalResult:
            called_signals.append("ai_signal")
            return SignalResult("ai_signal", 0, False)

        with patch("sentinel.risk.engine._AI_SIGNALS", [mock_ai_signal]):
            engine.score(event)

        assert "ai_signal" in called_signals


class TestConditionEvaluator:
    def test_eq_operator_match(self) -> None:
        event = make_event(actor_type="AI_AGENT")
        assert evaluate_condition(
            {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"}, event
        ) is True

    def test_eq_operator_no_match(self) -> None:
        event = make_event(actor_type="HUMAN")
        assert evaluate_condition(
            {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"}, event
        ) is False

    def test_gte_operator(self) -> None:
        event = make_event(risk_score=75)
        assert evaluate_condition(
            {"field": "risk_score", "operator": "gte", "value": 75}, event
        ) is True

    def test_gte_operator_below_threshold(self) -> None:
        event = make_event(risk_score=74)
        assert evaluate_condition(
            {"field": "risk_score", "operator": "gte", "value": 75}, event
        ) is False

    def test_in_operator(self) -> None:
        event = make_event(event_type="USER_LOGIN")
        assert evaluate_condition(
            {"field": "event_type", "operator": "in", "value": ["USER_LOGIN", "USER_LOGOUT"]},
            event,
        ) is True

    def test_not_in_operator(self) -> None:
        event = make_event(event_type="ADMIN_ACTION")
        assert evaluate_condition(
            {"field": "event_type", "operator": "not_in", "value": ["USER_LOGIN", "USER_LOGOUT"]},
            event,
        ) is True

    def test_and_compound_all_true(self) -> None:
        event = make_event(actor_type="AI_AGENT", risk_score=80)
        assert evaluate_condition(
            {
                "operator": "AND",
                "conditions": [
                    {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
                    {"field": "risk_score", "operator": "gte", "value": 75},
                ],
            },
            event,
        ) is True

    def test_and_compound_one_false(self) -> None:
        event = make_event(actor_type="HUMAN", risk_score=80)
        assert evaluate_condition(
            {
                "operator": "AND",
                "conditions": [
                    {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
                    {"field": "risk_score", "operator": "gte", "value": 75},
                ],
            },
            event,
        ) is False

    def test_or_compound_one_true(self) -> None:
        event = make_event(actor_type="HUMAN", risk_score=80)
        assert evaluate_condition(
            {
                "operator": "OR",
                "conditions": [
                    {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
                    {"field": "risk_score", "operator": "gte", "value": 75},
                ],
            },
            event,
        ) is True

    def test_metadata_subfield_access(self) -> None:
        event = make_event(metadata={"amount": 50000})
        assert evaluate_condition(
            {"field": "metadata.amount", "operator": "gte", "value": 10000},
            event,
        ) is True

    def test_is_null_operator(self) -> None:
        event = make_event(risk_score=None)
        assert evaluate_condition(
            {"field": "risk_score", "operator": "is_null", "value": None},
            event,
        ) is True

    def test_missing_field_raises(self) -> None:
        event = make_event()
        with pytest.raises(ConditionEvaluationError, match="missing 'field'"):
            evaluate_condition({"operator": "eq", "value": "x"}, event)

    def test_unknown_operator_raises(self) -> None:
        event = make_event()
        with pytest.raises(ConditionEvaluationError, match="Unknown operator"):
            evaluate_condition(
                {"field": "actor_type", "operator": "UNKNOWN", "value": "x"}, event
            )

    def test_none_risk_score_does_not_crash_gte(self) -> None:
        event = make_event(risk_score=None)
        result = evaluate_condition(
            {"field": "risk_score", "operator": "gte", "value": 75}, event
        )
        assert result is False
