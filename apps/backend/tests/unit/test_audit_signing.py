"""
Unit Tests — Audit Event Signing.

Tests HMAC-SHA256 signature computation and verification.
Pure unit tests — no database, no network.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from sentinel.audit.signing import compute_event_signature, verify_event_signature

# Fixed values for deterministic tests
_EVENT_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_CREATED_AT = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
_SECRET = "test-secret-key-for-unit-tests-only"


class TestComputeEventSignature:
    def test_returns_64_char_hex_string(self) -> None:
        sig = compute_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
            secret_key=_SECRET,
        )
        assert isinstance(sig, str)
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_same_inputs_produce_same_signature(self) -> None:
        kwargs = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            secret_key=_SECRET,
        )
        sig1 = compute_event_signature(**kwargs)
        sig2 = compute_event_signature(**kwargs)
        assert sig1 == sig2

    def test_different_event_types_produce_different_signatures(self) -> None:
        base = dict(
            event_id=_EVENT_ID,
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
            secret_key=_SECRET,
        )
        sig1 = compute_event_signature(event_type="USER_LOGIN", **base)
        sig2 = compute_event_signature(event_type="USER_LOGOUT", **base)
        assert sig1 != sig2

    def test_different_actor_ids_produce_different_signatures(self) -> None:
        base = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
            secret_key=_SECRET,
        )
        sig1 = compute_event_signature(actor_id="actor-aaa", **base)
        sig2 = compute_event_signature(actor_id="actor-bbb", **base)
        assert sig1 != sig2

    def test_null_actor_id_produces_valid_signature(self) -> None:
        sig = compute_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN_FAILED",
            actor_id=None,
            actor_email="",
            created_at=_CREATED_AT,
            metadata={},
            secret_key=_SECRET,
        )
        assert len(sig) == 64

    def test_metadata_order_does_not_affect_signature(self) -> None:
        """JSON is sorted before hashing — key order must not matter."""
        base = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            secret_key=_SECRET,
        )
        sig1 = compute_event_signature(metadata={"b": 2, "a": 1}, **base)
        sig2 = compute_event_signature(metadata={"a": 1, "b": 2}, **base)
        assert sig1 == sig2

    def test_different_secrets_produce_different_signatures(self) -> None:
        base = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
        )
        sig1 = compute_event_signature(secret_key="secret-one", **base)
        sig2 = compute_event_signature(secret_key="secret-two", **base)
        assert sig1 != sig2

    def test_modified_email_invalidates_signature(self) -> None:
        base = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            created_at=_CREATED_AT,
            metadata={},
            secret_key=_SECRET,
        )
        sig_original = compute_event_signature(actor_email="original@sentinel.io", **base)
        sig_modified = compute_event_signature(actor_email="modified@sentinel.io", **base)
        assert sig_original != sig_modified

    def test_modified_metadata_invalidates_signature(self) -> None:
        base = dict(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            secret_key=_SECRET,
        )
        sig_original = compute_event_signature(metadata={"action": "login"}, **base)
        sig_modified = compute_event_signature(metadata={"action": "login", "tampered": True}, **base)
        assert sig_original != sig_modified


class TestVerifyEventSignature:
    def _valid_signature(self) -> str:
        return compute_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            secret_key=_SECRET,
        )

    def test_valid_signature_returns_true(self) -> None:
        sig = self._valid_signature()
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            stored_signature=sig,
            secret_key=_SECRET,
        )
        assert result is True

    def test_tampered_event_type_returns_false(self) -> None:
        sig = self._valid_signature()
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGOUT",  # tampered
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            stored_signature=sig,
            secret_key=_SECRET,
        )
        assert result is False

    def test_tampered_metadata_returns_false(self) -> None:
        sig = self._valid_signature()
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "9.9.9.9"},  # tampered
            stored_signature=sig,
            secret_key=_SECRET,
        )
        assert result is False

    def test_tampered_actor_returns_false(self) -> None:
        sig = self._valid_signature()
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="different-actor",  # tampered
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            stored_signature=sig,
            secret_key=_SECRET,
        )
        assert result is False

    def test_wrong_secret_returns_false(self) -> None:
        sig = self._valid_signature()
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={"ip": "1.2.3.4"},
            stored_signature=sig,
            secret_key="wrong-secret",
        )
        assert result is False

    def test_corrupted_signature_returns_false(self) -> None:
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
            stored_signature="a" * 64,  # garbage
            secret_key=_SECRET,
        )
        assert result is False

    def test_empty_signature_returns_false(self) -> None:
        result = verify_event_signature(
            event_id=_EVENT_ID,
            event_type="USER_LOGIN",
            actor_id="actor-123",
            actor_email="user@sentinel.io",
            created_at=_CREATED_AT,
            metadata={},
            stored_signature="",
            secret_key=_SECRET,
        )
        assert result is False
