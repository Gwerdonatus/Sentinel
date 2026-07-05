"""
sentinel-sdk — Python client for the Sentinel security platform.

Quick start:
    pip install sentinel-sdk

    from sentinel_sdk import SentinelClient

    client = SentinelClient(api_key="sk_live_...")
    client.record("USER_LOGIN", actor_email="user@company.com", actor_ip="1.2.3.4")
"""

from sentinel_sdk.client import AsyncSentinelClient, SentinelClient, SentinelSDKError

__version__ = "0.5.0"
__all__ = ["SentinelClient", "AsyncSentinelClient", "SentinelSDKError"]
