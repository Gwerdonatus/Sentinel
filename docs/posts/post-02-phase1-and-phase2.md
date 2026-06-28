# Building Sentinel: Phase 1 Foundation + Phase 2 Identity & Audit Ledger

*This is the technical companion to [The Security Problem Every Fintech Ignores](#). If you haven't read that first, start there — it explains why Sentinel exists.*

We're building Sentinel in public. This post covers the first two phases: what we built, the decisions we made, and the reasoning behind each one. Everything is open source and the code is on GitHub.

---

## The Approach

Before writing a single line of application code, we designed the system correctly. That means a production-grade monorepo structure, documented architectural decisions, and an observability stack wired in from day one — not retrofitted later.

Two rules guided every decision:

1. **No shortcuts that create structural debt.** If a better approach exists, use it and document why.
2. **Future phases must not require structural refactoring.** The foundation has to support everything that comes after it.

---

## Phase 1: Foundation

### Repository Structure

Sentinel is a monorepo with three runtime components:

```
sentinel/
├── apps/
│   ├── backend/     # Django REST API
│   ├── frontend/    # Next.js 15 dashboard
│   └── worker/      # Celery task queue
├── infra/           # Docker, Nginx, Prometheus, Grafana
└── docs/            # Architecture, ADRs, roadmap
```

A monorepo for this stage is the right call. The event schema, API contracts, and TypeScript types are shared between frontend and backend. Atomic commits across the stack are possible. One CI pipeline covers everything.

### Technology Decisions

**Django 5.x, not FastAPI.** Sentinel is a security platform, not a high-throughput API gateway. Django's default security posture — CSRF protection, XSS filtering, SQL injection prevention, secure password hashing, admin interface — is directly relevant. FastAPI is faster but ships with none of these defaults. We'd spend engineering time rebuilding what Django provides for free.

**Celery + Redis for Phase 1, Kafka for Phase 2+.** Introducing Kafka before the event schema exists means either committing to a schema too early or designing a meaningless generic envelope. Both are worse than deferring. The task interface is abstracted so swapping the transport requires no business logic changes.

**Cursor-based pagination from day one.** The audit log will have millions of rows. `OFFSET` pagination degrades as the table grows — `OFFSET 1000000` forces the database to scan and skip a million rows every time. Cursor pagination is constant-time regardless of dataset size.

**UUID primary keys everywhere.** Sequential integer IDs expose record counts, enable enumeration attacks, and don't work across distributed systems. UUIDs are non-enumerable and can be generated without database coordination — critical for Kafka producers in Phase 2 that need to assign event IDs before insertion.

### Observability First

The biggest infrastructure decision in Phase 1 was instrumenting OpenTelemetry *before* any business logic exists.

Every HTTP request gets a `trace_id` and `request_id` injected at middleware level before reaching a view. These propagate through every log line, every database query span, every Celery task. When something goes wrong in production, the investigation starts with a `request_id` from the error response and ends with a complete picture of every operation that request touched.

Three middleware layers handle this:

```python
# Request ID — UUID injected before anything else
class RequestIDMiddleware:
    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response

# Trace context — W3C traceparent propagation
class TraceContextMiddleware:
    def __call__(self, request):
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            structlog.contextvars.bind_contextvars(
                trace_id=format(span_context.trace_id, "032x"),
                span_id=format(span_context.span_id, "016x"),
            )
        return self.get_response(request)
```

All logs are structured JSON in production. Every log line includes `trace_id`, `span_id`, `request_id`, `user_id`, `method`, `path`. No unstructured strings that require regex parsing to query.

### The Service/Repository Pattern

Views in Sentinel are deliberately thin. No database queries. No business logic. They validate input, call a service, and return a response.

```
HTTP Request → View (validate + call) → Service (logic) → Repository (DB) → PostgreSQL
```

This matters because the same service function can be called from a view, a Celery task, a management command, or a test — without any HTTP dependency. When the risk engine in Phase 3 needs to compute a risk score, it calls `AuditEventService.list()` directly. If the logic lived in a view, that's impossible.

### Health Endpoints

Three endpoints, deliberately separated:

- `GET /health/live/` — is this process running? Never checks dependencies. Used by Kubernetes liveness probes to decide whether to restart the pod.
- `GET /health/ready/` — can this instance serve traffic? Checks PostgreSQL and Redis. Returns 503 if either is down. Used by load balancers to pull unhealthy instances from rotation.
- `GET /health/` — full summary with latency per component. Used by Grafana and engineers during incidents.

The separation matters. If Redis goes down, we want requests routed to healthy instances — not the pod restarted (which won't fix Redis). Liveness and readiness serve different purposes and must never be conflated.

---

## Phase 2: Identity & Audit Ledger

Phase 2 is where Sentinel starts doing what it was built for.

### Custom User Model

The first decision was `AbstractBaseUser` over `AbstractUser`. Django's `AbstractUser` ships with `username`, `first_name`, `last_name`, groups, and permission tables. None of these are relevant to Sentinel. We need `email` as the login identifier and `role` as a direct column — not Django's M2M group system.

```python
class SentinelUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,  # ADMIN | AUDITOR | ANALYST | VIEWER
        default=Role.VIEWER,
        db_index=True,
    )
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    must_change_password = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
```

This is set as `AUTH_USER_MODEL = "sentinel_auth.SentinelUser"` in settings before the first migration. Changing this after migrations exist is a painful multi-step migration. This is the correct permanent configuration.

### JWT Authentication with Redis Blacklisting

`djangorestframework-simplejwt` handles token generation. The non-obvious decision is where to store the blacklist.

simplejwt ships with a database-backed blacklist. Every authenticated request checks two tables. That's a DB query on your hottest path — the authentication check — for every single API call.

We blacklist JTIs in Redis instead:

```python
_BLACKLIST_PREFIX = "sentinel:jwt:blacklist:"

def _blacklist_jti(jti: str, ttl_seconds: int) -> None:
    cache.set(f"{_BLACKLIST_PREFIX}{jti}", "1", timeout=ttl_seconds)

def _is_blacklisted(jti: str) -> bool:
    return cache.get(f"{_BLACKLIST_PREFIX}{jti}") is not None
```

O(1) lookup. TTL set to match refresh token lifetime — keys auto-expire when the token would have expired anyway. No cleanup job. No DB hit on the auth path.

**Refresh token rotation** is implemented manually (not simplejwt's built-in rotation). Every refresh call:
1. Validates the submitted token
2. Checks it against the Redis blacklist
3. If clean: blacklists the consumed JTI immediately
4. Issues a fresh access + refresh pair

If a refresh token is stolen and used, the next legitimate refresh attempt will detect the reuse and force re-authentication. This is the standard rotation security model.

### RBAC Without Django Groups

Four roles: `ADMIN`, `AUDITOR`, `ANALYST`, `VIEWER`. Role is stored as a `CharField` on the User model — not Django groups. DRF permission classes enforce it:

```python
class IsAuditorOrAbove(BasePermission):
    _allowed = {Role.ADMIN, Role.AUDITOR}

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self._allowed
        )
```

The role is embedded in the JWT payload at token issuance. Authorization checks require zero database queries — the information is in the token.

### The Immutable Audit Ledger

The audit event model is the core of Sentinel. Every security-relevant action produces one. Once written, it must never change.

```python
class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # WHO — denormalized snapshots, not foreign keys
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_email = models.EmailField(blank=True, default="")
    actor_role = models.CharField(max_length=20, blank=True, default="")
    actor_ip = models.GenericIPAddressField(null=True, blank=True)

    # WHAT
    event_type = models.CharField(max_length=64, choices=AuditEventType.choices, db_index=True)

    # WHAT WAS AFFECTED
    resource_type = models.CharField(max_length=64, blank=True, default="")
    resource_id = models.CharField(max_length=128, blank=True, default="")

    # CONTEXT
    metadata = models.JSONField(default=dict)
    request_id = models.CharField(max_length=64, blank=True, default="")

    # TAMPER EVIDENCE
    signature = models.CharField(max_length=64, blank=True, default="")

    # WHEN — future partition key
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # No updated_at — this table is append-only by design
```

Note the denormalized actor fields. We store the email and role *at the time of the event* — not a foreign key to the user. User records change. Audit records must not. If a user's email changes after an event, the audit record still accurately reflects who performed the action at the time.

**Immutability is enforced at three layers:**

1. **Repository layer** — `update()` and `delete()` raise `NotImplementedError` unconditionally.
2. **Django admin** — `has_change_permission` and `has_delete_permission` return `False`.
3. **HMAC-SHA256 signatures** — detects tampering even at the database level.

### HMAC Signature Scheme

Every event is signed at creation:

```python
def compute_event_signature(event_id, event_type, actor_id, actor_email,
                             created_at, metadata, secret_key):
    payload_json = json.dumps(metadata, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    message = "|".join([
        str(event_id),
        event_type,
        str(actor_id) if actor_id else "",
        actor_email,
        created_at.isoformat(),
        payload_hash,
    ])

    return hmac.new(
        key=secret_key.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
```

The metadata is hashed before inclusion — this handles large payloads efficiently while still covering them in the signature. JSON is sorted by key before hashing so key insertion order doesn't affect the signature.

Verification uses `hmac.compare_digest` — constant-time comparison that prevents timing attacks.

Any modification to any signed field — event type, actor, metadata, or timestamp — will produce a signature mismatch detectable via `GET /api/v1/events/{id}/verify/`.

### The @audit_action Decorator

The practical problem with audit logging is that engineers forget to do it. The `@audit_action` decorator makes forgetting impossible by wrapping the view method:

```python
class UserCreateView(APIView):
    @audit_action(
        event_type="USER_CREATED",
        resource_type="user",
        get_resource_id=lambda req, resp: resp.data.get("id"),
    )
    def post(self, request):
        # Create the user...
        return Response(user_data, status=201)
```

The decorator fires after a successful response (2xx). It records who made the request, what was affected, and the full context — without the view knowing anything about audit recording. Async by default via Celery; synchronous mode available where hard audit requirements demand it.

---

## What's Next

**Phase 3: Risk Intelligence & Alerting**
- Behavioral baseline per actor
- Real-time risk scoring on every event (impossible travel, velocity spikes, new device)
- Alert rule engine with a condition DSL
- API key management with HMAC-SHA256 hashed storage
- Webhook processing and notification delivery

The audit ledger built in Phase 2 is the input to the risk engine. Every event we now record cleanly becomes a signal the risk engine can act on.

---

## The Code

Everything is on GitHub: [github.com/your-org/sentinel](https://github.com/your-org/sentinel)

Current state: `v0.2.0` — Phase 1 + Phase 2 complete.

The repo includes 11 ADRs documenting every major architectural decision, 11 test files targeting 90%+ coverage, and a Docker Compose stack that brings up the complete environment in one command.

*Next post: Phase 3 — Risk Intelligence. We'll build the engine that scores every event in real time and fires alerts when the score crosses a threshold.*
