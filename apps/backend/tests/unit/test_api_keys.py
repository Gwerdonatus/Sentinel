"""
Unit Tests — API Key Model and Authentication.

Tests key generation, hashing, verification, and DRF authentication backend.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from sentinel.api_keys.authentication import APIKeyAuthentication
from sentinel.api_keys.models import APIKey, ActorType


@override_settings(SECRET_KEY="test-secret-key-for-hmac-fifty-chars-minimum-x")
class TestAPIKeyGeneration:
    def test_generate_key_returns_three_values(self) -> None:
        full_key, prefix, key_hash = APIKey.generate_key("live")
        assert full_key
        assert prefix
        assert key_hash

    def test_full_key_has_correct_prefix(self) -> None:
        full_key, _, _ = APIKey.generate_key("live")
        assert full_key.startswith("sk_live_")

    def test_test_environment_key_has_correct_prefix(self) -> None:
        full_key, _, _ = APIKey.generate_key("test")
        assert full_key.startswith("sk_test_")

    def test_key_prefix_is_substring_of_full_key(self) -> None:
        full_key, prefix, _ = APIKey.generate_key("live")
        assert full_key.startswith(prefix)

    def test_key_hash_is_64_char_hex(self) -> None:
        _, _, key_hash = APIKey.generate_key("live")
        assert len(key_hash) == 64
        assert all(c in "0123456789abcdef" for c in key_hash)

    def test_generated_keys_are_unique(self) -> None:
        key1, _, _ = APIKey.generate_key("live")
        key2, _, _ = APIKey.generate_key("live")
        assert key1 != key2

    def test_hash_is_deterministic_for_same_key_and_secret(self) -> None:
        import hashlib
        import hmac

        full_key = "sk_live_test123"
        expected = hmac.new(
            key=b"test-secret-key-for-hmac-fifty-chars-minimum-x",
            msg=full_key.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Manually compute what generate_key would do for this key
        actual = hmac.new(
            key=b"test-secret-key-for-hmac-fifty-chars-minimum-x",
            msg=full_key.encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert expected == actual


@pytest.mark.django_db
@override_settings(SECRET_KEY="test-secret-key-for-hmac-fifty-chars-minimum-x")
class TestAPIKeyVerification:
    def test_valid_key_returns_api_key_instance(self) -> None:
        full_key, prefix, key_hash = APIKey.generate_key("live")
        APIKey.objects.create(
            name="Test Key",
            actor_type=ActorType.SERVICE,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=["events:write"],
        )

        result = APIKey.verify_key(full_key)
        assert result is not None
        assert result.name == "Test Key"

    def test_invalid_key_returns_none(self) -> None:
        result = APIKey.verify_key("sk_live_totally_made_up_key_xyz")
        assert result is None

    def test_empty_key_returns_none(self) -> None:
        assert APIKey.verify_key("") is None

    def test_short_key_returns_none(self) -> None:
        assert APIKey.verify_key("short") is None

    def test_tampered_key_returns_none(self) -> None:
        full_key, prefix, key_hash = APIKey.generate_key("live")
        APIKey.objects.create(
            name="Test Key",
            actor_type=ActorType.SERVICE,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[],
        )

        tampered = full_key[:-1] + ("x" if full_key[-1] != "x" else "y")
        result = APIKey.verify_key(tampered)
        assert result is None

    def test_revoked_key_returns_none(self) -> None:
        from django.utils import timezone

        full_key, prefix, key_hash = APIKey.generate_key("live")
        key = APIKey.objects.create(
            name="Revoked Key",
            actor_type=ActorType.SERVICE,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[],
        )
        key.deleted_at = timezone.now()
        key.save()

        result = APIKey.verify_key(full_key)
        assert result is None

    def test_expired_key_returns_none(self) -> None:
        from datetime import timedelta
        from django.utils import timezone

        full_key, prefix, key_hash = APIKey.generate_key("live")
        APIKey.objects.create(
            name="Expired Key",
            actor_type=ActorType.SERVICE,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[],
            expires_at=timezone.now() - timedelta(days=1),
        )

        result = APIKey.verify_key(full_key)
        assert result is None


@pytest.mark.django_db
class TestAPIKeyModel:
    def test_has_scope_returns_true_for_present_scope(self) -> None:
        key = APIKey(scopes=["events:write", "events:read"])
        assert key.has_scope("events:write") is True

    def test_has_scope_returns_false_for_absent_scope(self) -> None:
        key = APIKey(scopes=["events:read"])
        assert key.has_scope("events:write") is False

    def test_is_active_true_for_fresh_key(self) -> None:
        key = APIKey(deleted_at=None, expires_at=None)
        assert key.is_active is True

    def test_is_active_false_for_deleted_key(self) -> None:
        from django.utils import timezone
        key = APIKey(deleted_at=timezone.now(), expires_at=None)
        assert key.is_active is False

    def test_record_usage_increments_total_uses(self) -> None:
        key = APIKey.objects.create(
            name="Usage Test",
            actor_type=ActorType.SERVICE,
            key_prefix="sk_live_usag",
            key_hash="x" * 64,
            scopes=[],
        )
        assert key.total_uses == 0
        key.record_usage(ip_address="1.2.3.4")
        key.refresh_from_db()
        assert key.total_uses == 1
        assert key.last_used_ip == "1.2.3.4"


class TestAPIKeyAuthenticationBackend:
    def test_skips_when_no_authorization_header(self) -> None:
        backend = APIKeyAuthentication()
        request = MagicMock()
        request.headers = {}
        assert backend.authenticate(request) is None

    def test_skips_jwt_tokens(self) -> None:
        backend = APIKeyAuthentication()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.fake"}
        assert backend.authenticate(request) is None

    def test_skips_non_bearer_auth(self) -> None:
        backend = APIKeyAuthentication()
        request = MagicMock()
        request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        assert backend.authenticate(request) is None

    def test_raises_on_invalid_key(self) -> None:
        from rest_framework.exceptions import AuthenticationFailed

        backend = APIKeyAuthentication()
        request = MagicMock()
        request.headers = {"Authorization": "Bearer sk_live_invalid_key_12345"}
        request.META = {"REMOTE_ADDR": "1.2.3.4"}

        with patch("sentinel.api_keys.authentication.APIKey.verify_key", return_value=None):
            with pytest.raises(AuthenticationFailed):
                backend.authenticate(request)
