# Building Sentinel: Kafka, Multi-tenancy & Python SDK

*Technical companion to [The Infrastructure Question Nobody Asks Until It's Urgent](#). Read that first.*

Phase 5 adds the infrastructure that makes Sentinel production-viable at scale: row-level tenant isolation, Kafka event streaming, and a Python SDK that reduces adoption to three lines of code. Three distinct engineering problems with three distinct design decisions worth explaining.

Code: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel) — tagged `v0.5.0`.

---

## Tenant Isolation: The Queryset Manager Pattern

The isolation mechanism is a custom Django manager that applies `filter(tenant_id=...)` automatically. Every scoped model inherits `TenantScopedModel`:

```python
class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant: object) -> "TenantQuerySet":
        if tenant is None:
            return self  # Superuser — no scoping
        return self.filter(tenant_id=getattr(tenant, "id", tenant))

class TenantManager(models.Manager):
    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant: object) -> TenantQuerySet:
        return self.get_queryset().for_tenant(tenant)

class TenantScopedModel(models.Model):
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True)
    objects = TenantManager()

    class Meta:
        abstract = True
```

Usage in views is one additional call:

```python
def get(self, request: Request, ...) -> Response:
    tenant = get_tenant_from_request(request)
    events = AuditEvent.objects.for_tenant(tenant).filter(
        event_type=event_type, created_at__gte=from_dt
    )
```

The tenant is resolved from the request once and cached on `request._resolved_tenant`. Resolution order:

```python
def get_tenant_from_request(request: HttpRequest) -> Tenant | None:
    if hasattr(request, "_resolved_tenant"):
        return request._resolved_tenant

    # API key auth — tenant stored on the key
    if hasattr(request, "auth") and hasattr(request.auth, "tenant"):
        tenant = request.auth.tenant

    # JWT auth — tenant_id embedded as a claim
    elif hasattr(request, "auth") and hasattr(request.auth, "payload"):
        tenant_id_str = request.auth.payload.get("tenant_id")
        if tenant_id_str:
            tenant = Tenant.objects.get(id=uuid.UUID(tenant_id_str), is_active=True)

    request._resolved_tenant = tenant
    return tenant
```

The `tenant_id` migration is additive — existing rows get `NULL` (platform-level), new rows get the owning tenant's UUID. The migration itself touches four tables at once: `AuditEvent`, `Alert`, `AlertRule`, and `APIKey`:

```python
# 0002_add_tenant_id_to_models.py
operations = [
    migrations.AddField(model_name="auditevent", name="tenant_id",
        field=models.UUIDField(blank=True, db_index=True, null=True)),
    migrations.AddIndex(model_name="auditevent",
        index=models.Index(fields=["tenant_id", "created_at"], name="idx_audit_tenant_time")),
    # ... same for Alert, AlertRule, APIKey
]
```

One migration, all tables, non-breaking. Existing deployments keep working — `NULL` tenant_id records are visible only to superusers.

Each tenant also gets a Kafka topic prefix computed on first save:

```python
def save(self, *args, **kwargs):
    if not self.kafka_topic_prefix:
        self.kafka_topic_prefix = f"sentinel.{self.id}"
    super().save(*args, **kwargs)

def get_kafka_topic(self, topic_type: str) -> str:
    return f"{self.kafka_topic_prefix}.{topic_type}"
    # → "sentinel.{uuid}.audit.events"
```

---

## Kafka: Producer Design

The producer is a process-level singleton. One connection per Django worker process, shared across all requests in that process:

```python
_producer: Producer | None = None

def get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "acks": "all",                 # All replicas must ack
            "enable.idempotence": True,    # Exactly-once semantics
            "compression.type": "snappy",
            "linger.ms": 5,               # 5ms batching window
            "batch.size": 32768,           # 32KB batches
        })
    return _producer
```

The `_NoOpProducer` fallback is the feature that makes development frictionless:

```python
try:
    from confluent_kafka import Producer
    _producer = Producer({...})
except ImportError:
    logger.warning("kafka_not_available — events will not be published to Kafka")
    _producer = _NoOpProducer()
```

`_NoOpProducer` has the same interface as the real producer but does nothing. A developer running Sentinel locally without Kafka gets no errors, no crashes — just a log line. This is a product decision: the audit pipeline's correctness must not depend on Kafka being present. PostgreSQL is the source of truth; Kafka is the distribution layer.

Publishing after DB write:

```python
def publish_audit_event(event: AuditEvent) -> None:
    try:
        producer = get_producer()
        topic = _get_topic_for_event(event)
        payload = _serialize_audit_event(event)  # JSON, schema_version: "1.0"

        producer.produce(
            topic=topic,
            key=str(event.id).encode(),   # Partition by event ID
            value=json.dumps(payload).encode(),
            callback=_delivery_callback,
        )
        producer.poll(0)  # Trigger delivery callbacks without blocking

    except Exception as exc:
        logger.error("kafka_publish_failed", event_id=str(event.id), error=str(exc))
        # Never raise — Kafka failure must not break the audit pipeline
```

The `never raise` rule is enforced in the exception handler. If Kafka is unreachable, the event is already in PostgreSQL. The only consequence of a failed publish is that downstream consumers don't see the event until a backfill runs.

Every message carries a `schema_version` field:

```python
payload = {
    "schema_version": "1.0",
    "id": str(event.id),
    "tenant_id": str(event.tenant_id) if event.tenant_id else None,
    "event_type": event.event_type,
    "actor_type": event.actor_type,
    "agent_name": event.agent_name,
    # ... other fields
    "created_at": event.created_at.isoformat(),
}
```

Consumers check `schema_version` before processing. When the schema evolves in Phase 6, consumers can handle both `"1.0"` and `"2.0"` during the transition window without a hard cutover.

---

## Kafka: Consumer Design

The consumer runs as a separate process — `python manage.py run_kafka_consumer` — which becomes its own Docker service in the compose stack:

```yaml
kafka-consumer:
  command: python manage.py run_kafka_consumer
  depends_on:
    kafka:
      condition: service_healthy
```

Three consumer design decisions worth explaining:

**Manual offset commit.** `enable.auto.commit: false` means the consumer commits the offset only after the risk engine has processed the event successfully. If the process crashes mid-processing, the event is reprocessed on restart:

```python
self._process_message(msg)
# ↑ risk scoring happens here

self._consumer.commit(msg)  # Only after success
```

This gives at-least-once delivery semantics. The risk engine is idempotent for the same `event_id` (it overwrites, not appends), so reprocessing is safe.

**Partition assignment by actor ID.** Events from the same actor are always processed by the same consumer instance (assuming consistent hash partitioning, which Kafka does by key). This matters for the velocity spike signal — it needs sequential event ordering per actor. If two consumer instances processed events from the same actor in parallel, the ordering guarantee would break.

**Graceful shutdown on SIGTERM.** Kubernetes terminates pods with SIGTERM before SIGKILL:

```python
signal.signal(signal.SIGTERM, self._handle_shutdown)
signal.signal(signal.SIGINT, self._handle_shutdown)

def _handle_shutdown(self, signum, frame):
    self._running = False
    # The while loop exits on next iteration, consumer.close() is called in finally
```

The poll loop checks `self._running` on every iteration. SIGTERM sets it to `False`. The current message finishes processing, the offset is committed, and the consumer closes cleanly. No events are lost during pod rotation.

---

## The Python SDK

The SDK design philosophy: the caller should never have to think about HTTP.

```python
# Everything the caller should NOT have to write themselves:
# - Authorization header formatting
# - JSON serialization
# - Retry on network failure
# - Error response parsing
# - Actor type and agent name on every call
# - Request ID generation

# What they write instead:
client.record("TRANSFER_INITIATED", resource_type="transfer", resource_id=txn_id)
```

The `fail_silent` default deserves explanation. Sentinel is security *infrastructure* — it records what happens to other systems. If the infrastructure itself can take down those systems by raising on a failed HTTP call, it defeats the purpose. A payment service that crashes because Sentinel was briefly unreachable is worse than a payment service that processed the transaction without recording it — at least the payment worked, and the gap in the audit log is visible and recoverable.

`fail_silent=True` means network errors and API errors are logged (visible in your observability stack) but never raised. The calling service continues. The audit gap is detectable and can be backfilled.

`fail_silent=False` exists for test environments specifically, where you want to catch integration issues immediately:

```python
# In production
client = SentinelClient(api_key="sk_live_...", fail_silent=True)

# In tests — surface errors immediately
client = SentinelClient(api_key="sk_test_...", fail_silent=False)
result = client.record("USER_LOGIN")
assert result is not None  # Would have raised if the call failed
```

For AI agents, the client is the identity carrier:

```python
# One client instance per agent — identity is structural, not per-call
fraud_detector = SentinelClient(
    api_key="sk_live_...",
    actor_type="AI_AGENT",
    agent_name="fraud-detector-v3",
    fail_silent=True,
)

# Every event from this client is attributed to fraud-detector-v3
fraud_detector.record(
    "TRANSFER_APPROVED",
    resource_type="transfer",
    resource_id=transfer_id,
    metadata={"confidence": 0.97, "model_version": "v3.2.1"},
)
```

The agent doesn't have to remember to set `actor_type` or `agent_name` on every call. It's set once at client construction. This is deliberate: the most likely integration mistake is forgetting attribution on some calls but not others, producing an audit log where some AI agent actions are correctly attributed and others appear as anonymous service calls. Making attribution structural eliminates the mistake.

The async client has identical semantics:

```python
async with AsyncSentinelClient(api_key="sk_live_...") as client:
    await client.record("USER_LOGIN", actor_email="user@company.com")
```

---

## Current Platform State

After Phase 5, the full Sentinel stack is:

| Component | Technology | Phase Delivered |
|---|---|---|
| Audit ledger | PostgreSQL, HMAC-signed | Phase 2 |
| JWT auth + RBAC | simplejwt, Redis blacklist | Phase 2 |
| AI actor identity | APIKey with actor_type/agent_name | Phase 3 |
| Risk scoring | Composite signals, 0-100 scale | Phase 3 |
| Alert rules | JSON conditions, 5 built-in rules | Phase 3 |
| Notification delivery | Slack, email, webhook | Phase 3 |
| Dashboard | Next.js, BFF auth, actor timeline | Phase 4 |
| Compliance reports | PDF/CSV/JSON, AI attribution | Phase 4 |
| Multi-tenancy | Row-level isolation, tenant_id | Phase 5 |
| Kafka streaming | Per-tenant topics, exactly-once | Phase 5 |
| Python SDK | sync + async, fail_silent | Phase 5 |

---

## What's Next

Phase 6 is the operational envelope: Kubernetes manifests, Prometheus alerting rules with SLA thresholds, the GitHub Actions CD pipeline that builds and deploys to a cluster, and the OpenAPI-to-SDK auto-generation pipeline that keeps the SDK's event type list automatically synchronized with the backend as new event types are added.

The architecture is stable. What remains is making deployment repeatable and operationally observable.

---

*Star the repo: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*

*v0.5.0 tagged. Phase 6 in progress.*
