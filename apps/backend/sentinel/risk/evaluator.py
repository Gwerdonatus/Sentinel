"""
Alert Rule Condition Evaluator.

Evaluates structured JSON conditions against AuditEvent instances.

Condition format:
    Simple:   {"field": "risk_score", "operator": "gte", "value": 75}
    Compound: {"operator": "AND", "conditions": [...]}
               {"operator": "OR",  "conditions": [...]}

Supported operators:
    eq, neq       — equality
    gt, gte       — greater than (numeric)
    lt, lte       — less than (numeric)
    in, not_in    — membership in list
    contains      — substring match (strings) or item in list
    is_null       — field is None/null

Supported fields (all AuditEvent columns):
    event_type, actor_type, actor_id, actor_email, actor_role, actor_ip,
    agent_name, resource_type, resource_id, risk_score, risk_level
    Plus metadata sub-fields: metadata.key_name
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sentinel.audit.models import AuditEvent
    from sentinel.risk.models import AlertRule

logger = structlog.get_logger(__name__)


class ConditionEvaluationError(Exception):
    """Raised when a condition cannot be evaluated due to bad structure."""


def evaluate_condition(
    condition: dict[str, Any],
    event: "AuditEvent",
    risk_level: str = "",
) -> bool:
    """
    Evaluate a condition dict against an AuditEvent.

    Returns True if the event matches the condition, False otherwise.
    Raises ConditionEvaluationError on malformed conditions.
    """
    operator = condition.get("operator", "").lower()

    # Compound conditions
    if operator == "and":
        sub_conditions = condition.get("conditions", [])
        if not sub_conditions:
            raise ConditionEvaluationError("AND condition requires at least one sub-condition.")
        return all(evaluate_condition(c, event, risk_level) for c in sub_conditions)

    if operator == "or":
        sub_conditions = condition.get("conditions", [])
        if not sub_conditions:
            raise ConditionEvaluationError("OR condition requires at least one sub-condition.")
        return any(evaluate_condition(c, event, risk_level) for c in sub_conditions)

    # Simple conditions
    field = condition.get("field")
    value = condition.get("value")

    if not field:
        raise ConditionEvaluationError("Condition missing 'field'.")
    if not operator:
        raise ConditionEvaluationError("Condition missing 'operator'.")

    actual = _get_field_value(event, field, risk_level)
    return _apply_operator(operator, actual, value, field)


def evaluate_rule(
    rule: "AlertRule",
    event: "AuditEvent",
    risk_level: str = "",
) -> bool:
    """
    Evaluate an AlertRule against an AuditEvent.

    Returns True if the rule fires (event matches condition).
    Returns False on evaluation errors (rules should not crash the pipeline).
    """
    try:
        return evaluate_condition(rule.condition, event, risk_level)
    except ConditionEvaluationError as exc:
        logger.error(
            "rule_condition_error",
            rule_id=str(rule.id),
            rule_name=rule.name,
            error=str(exc),
        )
        return False
    except Exception as exc:
        logger.error(
            "rule_evaluation_error",
            rule_id=str(rule.id),
            rule_name=rule.name,
            error=str(exc),
            exc_info=True,
        )
        return False


def _get_field_value(
    event: "AuditEvent",
    field: str,
    risk_level: str = "",
) -> Any:
    """Extract a field value from the event, supporting metadata sub-fields."""
    if field == "risk_level":
        return risk_level

    if field.startswith("metadata."):
        key = field[len("metadata."):]
        return (event.metadata or {}).get(key)

    return getattr(event, field, None)


def _apply_operator(operator: str, actual: Any, expected: Any, field: str) -> bool:
    """Apply a comparison operator between actual and expected values."""
    try:
        if operator == "eq":
            return actual == expected
        if operator == "neq":
            return actual != expected
        if operator == "gt":
            return actual is not None and actual > expected
        if operator == "gte":
            return actual is not None and actual >= expected
        if operator == "lt":
            return actual is not None and actual < expected
        if operator == "lte":
            return actual is not None and actual <= expected
        if operator == "in":
            return actual in (expected or [])
        if operator == "not_in":
            return actual not in (expected or [])
        if operator == "contains":
            if isinstance(actual, str):
                return str(expected) in actual
            if isinstance(actual, list):
                return expected in actual
            return False
        if operator == "is_null":
            return actual is None
        raise ConditionEvaluationError(f"Unknown operator: {operator!r}")
    except TypeError:
        return False
