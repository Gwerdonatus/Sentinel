# sentinel-sdk

Python SDK for the [Sentinel](https://github.com/Gwerdonatus/Sentinel) security and audit platform.

## Installation

```bash
pip install sentinel-sdk
```

## Quick Start

```python
from sentinel_sdk import SentinelClient

client = SentinelClient(
    api_key="sk_live_...",
    base_url="https://sentinel.your-company.com",
)

# Record a user login
client.record(
    "USER_LOGIN",
    actor_email="user@company.com",
    actor_ip="1.2.3.4",
    actor_id="550e8400-e29b-41d4-a716-446655440000",
)

# Record a financial event
client.record(
    "TRANSFER_INITIATED",
    resource_type="transfer",
    resource_id="txn_abc123",
    metadata={
        "amount": 5000,
        "currency": "NGN",
        "destination_account": "****4532",
    },
)
```

## AI Agent Usage

Create an API key with `actor_type=AI_AGENT` and pass `agent_name` to the client. All events from this client are attributed to that AI agent:

```python
from sentinel_sdk import SentinelClient

# One client per AI agent — agent identity is baked into the client
support_bot = SentinelClient(
    api_key="sk_live_...",  # Key created with actor_type=AI_AGENT
    actor_type="AI_AGENT",
    agent_name="support-bot-v2",
)

# Every event is attributed to support-bot-v2 automatically
support_bot.record(
    "USER_LOGIN",  # Support bot authenticated a user session
    resource_type="user",
    resource_id=user_id,
    metadata={"session_id": session_id, "channel": "support_chat"},
)
```

## Async Usage

```python
from sentinel_sdk import AsyncSentinelClient

async def handle_transfer(transfer_id: str, user_id: str):
    async with AsyncSentinelClient(api_key="sk_live_...") as client:
        await client.record(
            "TRANSFER_INITIATED",
            actor_id=user_id,
            resource_type="transfer",
            resource_id=transfer_id,
        )
```

## Configuration

| Parameter | Default | Description |
|---|---|---|
| `api_key` | `$SENTINEL_API_KEY` | Required. Your `sk_live_` or `sk_test_` key |
| `base_url` | `$SENTINEL_BASE_URL` | Your Sentinel instance URL |
| `timeout` | `5.0` | Request timeout in seconds |
| `fail_silent` | `True` | Log errors without raising. Set `False` in tests |
| `actor_type` | `"SERVICE"` | Default: `"HUMAN_API"`, `"SERVICE"`, or `"AI_AGENT"` |
| `agent_name` | `""` | For AI_AGENT: the agent's machine-readable name |

## Available Event Types

```python
# Authentication
"USER_LOGIN", "USER_LOGOUT", "USER_LOGIN_FAILED",
"PASSWORD_RESET_REQUESTED", "PASSWORD_RESET_COMPLETED", "PASSWORD_CHANGED",

# User management
"USER_CREATED", "USER_DEACTIVATED", "USER_ROLE_CHANGED",

# API keys
"API_KEY_CREATED", "API_KEY_ROTATED", "API_KEY_REVOKED",

# Financial
"TRANSFER_INITIATED", "TRANSFER_APPROVED", "TRANSFER_REJECTED",

# System
"ADMIN_ACTION", "PERMISSION_CHANGED", "WEBHOOK_DELIVERED", "WEBHOOK_FAILED",
```

## Using with Django

```python
# middleware.py — record every authenticated request
from sentinel_sdk import SentinelClient

_sentinel = SentinelClient(api_key=settings.SENTINEL_API_KEY, fail_silent=True)

class SentinelAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated and request.method in ("POST", "PUT", "DELETE"):
            _sentinel.record(
                "ADMIN_ACTION",
                actor_id=str(request.user.id),
                actor_email=request.user.email,
                actor_ip=request.META.get("REMOTE_ADDR", ""),
                resource_type=request.path.split("/")[2] if request.path.count("/") >= 2 else "",
                metadata={"method": request.method, "path": request.path, "status": response.status_code},
            )
        return response
```

## Fail Silent vs Fail Loud

By default, `fail_silent=True` — network errors and API errors are logged but not raised. Your application continues normally even if Sentinel is temporarily unavailable.

Set `fail_silent=False` in tests and CI to catch integration issues:

```python
# In tests
client = SentinelClient(api_key="sk_test_...", fail_silent=False)
```

## License

MIT — see [LICENSE](../LICENSE)
