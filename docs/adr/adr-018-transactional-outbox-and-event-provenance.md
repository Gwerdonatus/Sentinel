# ADR-018: Transactional Outbox and Credential-Derived Event Identity

## Status

Accepted

## Context

Sentinel stores audit events in PostgreSQL and distributes them through Kafka for
risk scoring. Publishing directly after a database insert creates a dual-write
failure: the event may be committed while Kafka publication fails. Logging that
failure does not provide recovery.

External event producers also submit business context that cannot be treated as
authoritative identity. An authenticated agent must not be able to claim a
different actor ID, role, actor type, tenant, or source address in its payload.

## Decision

1. `AuditEvent` and `AuditOutbox` are committed in one PostgreSQL transaction.
2. A periodic Celery publisher drains pending outbox rows and marks them published
   only after Kafka acknowledges delivery.
3. Failed publication remains pending with bounded exponential backoff and the
   most recent error recorded for operations.
4. Kafka is the sole trigger for risk scoring. Celery handles outbox publication,
   notifications, reports, and scheduled command-style work.
5. API-key identity, actor type, agent name, tenant, request ID, and source address
   are derived by Sentinel. Clients may submit the business event type, affected
   resource, resource ID, and structured metadata.
6. API-key scopes are enforced at the endpoint (`events:write` and `events:read`).
7. Alert creation is unique per rule and audit event, making Kafka redelivery safe.

## Consequences

- Kafka outages no longer lose publication intent.
- Event processing is eventually consistent; the audit record can exist before a
  risk score is available.
- At-least-once Kafka consumption remains possible, so every consumer must be
  idempotent.
- The outbox publisher adds a small amount of database load and operational state.
- Sentinel authenticates who reported an event; it does not independently prove
  that every reported business detail is true.

## HMAC boundary

New events use signature format version 2, covering identity, resource, request,
timestamp, tenant, and metadata fields. Historical version-1 records remain
verifiable.

Per-record HMAC detects modification of signed fields. It does **not** prove that
an event was never deleted, that all events are correctly ordered, or that a party
with the signing key could not forge a replacement. Hash chaining or external
anchoring is a separate future decision.
