"""
Unit Tests — Sentinel SDK Client.

Tests client initialization, event recording, error handling, and
the fail_silent/fail_loud behavior. Uses respx to mock httpx.
"""

from __future__ import annotations

import pytest
import respx
import httpx

from sentinel_sdk.client import AsyncSentinelClient, SentinelClient, SentinelSDKError


class TestSentinelClientInit:
    def test_raises_without_api_key(self) -> None:
        import os
        os.environ.pop("SENTINEL_API_KEY", None)
        with pytest.raises(ValueError, match="API key is required"):
            SentinelClient()

    def test_accepts_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SENTINEL_API_KEY", "sk_live_test")
        client = SentinelClient()
        assert client._api_key == "sk_live_test"
        client.close()

    def test_accepts_api_key_as_arg(self) -> None:
        client = SentinelClient(api_key="sk_live_test")
        assert client._api_key == "sk_live_test"
        client.close()

    def test_default_actor_type_is_service(self) -> None:
        client = SentinelClient(api_key="sk_live_test")
        assert client._actor_type == "SERVICE"
        client.close()

    def test_agent_name_stored(self) -> None:
        client = SentinelClient(api_key="sk_live_test", agent_name="support-bot-v2")
        assert client._agent_name == "support-bot-v2"
        client.close()

    def test_fail_silent_default_is_true(self) -> None:
        client = SentinelClient(api_key="sk_live_test")
        assert client._fail_silent is True
        client.close()


@respx.mock
class TestSentinelClientRecord:
    def test_successful_record_returns_event_dict(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(201, json={
                "id": "abc-123",
                "event_type": "USER_LOGIN",
                "created_at": "2025-01-01T00:00:00Z",
            })
        )
        client = SentinelClient(api_key="sk_live_test", fail_silent=False)
        result = client.record("USER_LOGIN", actor_email="user@example.com")
        assert result is not None
        assert result["event_type"] == "USER_LOGIN"
        client.close()

    def test_agent_name_included_in_payload(self) -> None:
        route = respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(201, json={"id": "x", "event_type": "ADMIN_ACTION"})
        )
        client = SentinelClient(
            api_key="sk_live_test",
            actor_type="AI_AGENT",
            agent_name="fraud-detector-v3",
        )
        client.record("ADMIN_ACTION")

        request_body = route.calls.last.request.content
        import json
        payload = json.loads(request_body)
        assert payload["agent_name"] == "fraud-detector-v3"
        assert payload["actor_type"] == "AI_AGENT"
        client.close()

    def test_fail_silent_returns_none_on_error(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(500, json={"error": {"message": "Internal error"}})
        )
        client = SentinelClient(api_key="sk_live_test", fail_silent=True)
        result = client.record("USER_LOGIN")
        assert result is None
        client.close()

    def test_fail_loud_raises_on_error(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(422, json={"error": {"message": "Invalid event_type"}})
        )
        client = SentinelClient(api_key="sk_live_test", fail_silent=False)
        with pytest.raises(SentinelSDKError) as exc_info:
            client.record("INVALID_EVENT_TYPE")
        assert exc_info.value.status_code == 422
        client.close()

    def test_fail_silent_returns_none_on_network_error(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = SentinelClient(api_key="sk_live_test", fail_silent=True)
        result = client.record("USER_LOGIN")
        assert result is None
        client.close()

    def test_fail_loud_raises_on_network_error(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        client = SentinelClient(api_key="sk_live_test", fail_silent=False)
        with pytest.raises(SentinelSDKError):
            client.record("USER_LOGIN")
        client.close()

    def test_metadata_passed_correctly(self) -> None:
        route = respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(201, json={"id": "x", "event_type": "TRANSFER_INITIATED"})
        )
        client = SentinelClient(api_key="sk_live_test")
        client.record(
            "TRANSFER_INITIATED",
            resource_type="transfer",
            resource_id="txn_001",
            metadata={"amount": 5000, "currency": "NGN"},
        )
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["metadata"]["amount"] == 5000
        assert payload["resource_type"] == "transfer"
        assert payload["resource_id"] == "txn_001"
        client.close()


class TestSentinelClientContextManager:
    def test_sync_context_manager(self) -> None:
        with SentinelClient(api_key="sk_live_test") as client:
            assert client._api_key == "sk_live_test"
        # Client is closed — httpx client is also closed


@pytest.mark.asyncio
@respx.mock
class TestAsyncSentinelClient:
    async def test_async_record_returns_event(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(201, json={"id": "abc", "event_type": "USER_LOGIN"})
        )
        async with AsyncSentinelClient(api_key="sk_live_test", fail_silent=False) as client:
            result = await client.record("USER_LOGIN", actor_email="user@example.com")
        assert result is not None
        assert result["id"] == "abc"

    async def test_async_fail_silent(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(500, json={"error": {"message": "error"}})
        )
        async with AsyncSentinelClient(api_key="sk_live_test", fail_silent=True) as client:
            result = await client.record("USER_LOGIN")
        assert result is None

    async def test_async_fail_loud_raises(self) -> None:
        respx.post("https://api.sentinel.io/api/v1/events/ingest/").mock(
            return_value=httpx.Response(401, json={"error": {"message": "Unauthorized"}})
        )
        async with AsyncSentinelClient(api_key="sk_live_test", fail_silent=False) as client:
            with pytest.raises(SentinelSDKError) as exc_info:
                await client.record("USER_LOGIN")
        assert exc_info.value.status_code == 401
