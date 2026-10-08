"""
Audit Event Signing.

Produces and verifies versioned HMAC-SHA256 signatures for audit events.

The signature proves that the record has not been tampered with after
creation. Any modification to the signed fields (event_type, actor_id,
actor_email, created_at, or the payload hash) will invalidate the signature.

This is not encryption — it is tamper evidence. The signature is stored
alongside the record and can be recomputed at any time for verification.

Signature input:
    "{id}|{event_type}|{actor_id}|{actor_email}|{created_at_iso}|{payload_sha256}"

Where payload_sha256 is SHA256 of JSON-serialized metadata (sorted keys).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime


def compute_event_signature(
    event_id: uuid.UUID,
    event_type: str,
    actor_id: str | None,
    actor_email: str,
    created_at: datetime,
    metadata: dict[str, object],
    secret_key: str,
    *,
    version: int = 1,
    tenant_id: str | None = None,
    actor_type: str = "HUMAN",
    actor_role: str = "",
    actor_ip: str = "",
    agent_name: str = "",
    resource_type: str = "",
    resource_id: str = "",
    request_id: str = "",
) -> str:
    """
    Compute an HMAC-SHA256 signature for an audit event.

    Returns the hex digest (64 characters).
    """
    if version not in (1, 2):
        raise ValueError(f"Unsupported audit signature version: {version}")

    # Stable JSON serialization of the payload
    payload_json = json.dumps(metadata, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    if version == 1:
        message = "|".join(
            [
                str(event_id),
                event_type,
                str(actor_id) if actor_id else "",
                actor_email,
                created_at.isoformat(),
                payload_hash,
            ]
        )
    else:
        canonical_event = {
            "version": 2,
            "id": str(event_id),
            "tenant_id": str(tenant_id) if tenant_id else "",
            "event_type": event_type,
            "actor_id": str(actor_id) if actor_id else "",
            "actor_type": actor_type,
            "actor_email": actor_email,
            "actor_role": actor_role,
            "actor_ip": actor_ip,
            "agent_name": agent_name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_id": request_id,
            "created_at": created_at.isoformat(),
            "payload_sha256": payload_hash,
        }
        message = json.dumps(canonical_event, sort_keys=True, separators=(",", ":"))

    return hmac.new(
        key=secret_key.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_event_signature(
    event_id: uuid.UUID,
    event_type: str,
    actor_id: str | None,
    actor_email: str,
    created_at: datetime,
    metadata: dict[str, object],
    stored_signature: str,
    secret_key: str,
    *,
    version: int = 1,
    tenant_id: str | None = None,
    actor_type: str = "HUMAN",
    actor_role: str = "",
    actor_ip: str = "",
    agent_name: str = "",
    resource_type: str = "",
    resource_id: str = "",
    request_id: str = "",
) -> bool:
    """
    Verify a stored signature against recomputed values.

    Returns True if the signature is valid (record unmodified).
    Returns False if the signature does not match (tampered or corrupted).

    Uses hmac.compare_digest for constant-time comparison to prevent
    timing attacks.
    """
    expected = compute_event_signature(
        event_id=event_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_email=actor_email,
        created_at=created_at,
        metadata=metadata,
        secret_key=secret_key,
        version=version,
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_role=actor_role,
        actor_ip=actor_ip,
        agent_name=agent_name,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
    )
    return hmac.compare_digest(expected, stored_signature)
