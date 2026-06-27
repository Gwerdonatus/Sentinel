"""
Unit Tests — Health Check Logic.

Tests the CheckResult dataclass and check status behavior.
These are pure unit tests — no database or Redis is required.
"""

from __future__ import annotations

import pytest

from sentinel.core.health.checks import CheckResult, CheckStatus


class TestCheckResult:
    """Tests for the CheckResult data container."""

    def test_to_dict_includes_status_and_latency(self) -> None:
        result = CheckResult(name="database", status=CheckStatus.OK, latency_ms=12.5)
        data = result.to_dict()
        assert data["status"] == "ok"
        assert data["latency_ms"] == 12.5

    def test_to_dict_excludes_empty_message(self) -> None:
        result = CheckResult(name="database", status=CheckStatus.OK, latency_ms=5.0)
        data = result.to_dict()
        assert "message" not in data

    def test_to_dict_includes_message_when_set(self) -> None:
        result = CheckResult(
            name="redis",
            status=CheckStatus.ERROR,
            latency_ms=1001.0,
            message="Connection refused",
        )
        data = result.to_dict()
        assert data["message"] == "Connection refused"

    def test_to_dict_excludes_empty_metadata(self) -> None:
        result = CheckResult(name="database", status=CheckStatus.OK, latency_ms=5.0)
        data = result.to_dict()
        assert "metadata" not in data

    def test_to_dict_includes_metadata_when_set(self) -> None:
        result = CheckResult(
            name="database",
            status=CheckStatus.OK,
            latency_ms=5.0,
            metadata={"vendor": "postgresql"},
        )
        data = result.to_dict()
        assert data["metadata"] == {"vendor": "postgresql"}

    def test_check_status_values_are_strings(self) -> None:
        assert CheckStatus.OK.value == "ok"
        assert CheckStatus.ERROR.value == "error"
        assert CheckStatus.DEGRADED.value == "degraded"

    def test_check_status_is_comparable_to_string(self) -> None:
        """CheckStatus inherits from str — direct string comparison works."""
        assert CheckStatus.OK == "ok"
        assert CheckStatus.ERROR == "error"

    @pytest.mark.parametrize(
        "status,expected",
        [
            (CheckStatus.OK, True),
            (CheckStatus.ERROR, False),
            (CheckStatus.DEGRADED, False),
        ],
    )
    def test_only_ok_status_is_truthy_when_compared(
        self, status: CheckStatus, expected: bool
    ) -> None:
        """Verify status semantics for the health summary view logic."""
        result = CheckResult(name="test", status=status, latency_ms=1.0)
        is_healthy = result.status == CheckStatus.OK
        assert is_healthy is expected
