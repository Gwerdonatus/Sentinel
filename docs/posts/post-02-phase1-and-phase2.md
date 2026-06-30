# Building Sentinel: Foundation + Audit Ledger for the AI Era

*This is the technical companion to [The Missing Trust Layer in AI-Powered Financial Systems](#). Read that first for the problem context.*

We're building Sentinel in public. This post covers Phases 1 and 2: what we built, the decisions behind it, and how every technical choice connects back to the core problem — building a trust layer for financial systems where both humans and AI agents are actors.

The full code is on GitHub: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)

---

## The Design Constraint That Shaped Everything

Before writing code, we established one non-negotiable constraint:

**Every design decision must work for both human users and AI agents as first-class actors.**

This sounds obvious. In practice it changes a lot.

An audit system designed only for humans stores a `user_id`. An audit system designed for the AI era stores an `actor_id`, an `actor_type` (HUMAN, SERVICE, AI_AGENT), and enough context to reconstruct what kind of actor was responsible. The schema difference is small. The investigative capability difference is enormous.

A risk engine designed only for humans detects impossible travel. A risk engine designed for AI agents detects data volume anomalies, out-of-scope resource access, and behavioral drift in automated systems. These are different signals requiring different baselines.

We built Phase 1 and 2 as the foundation. Phase 3 adds the AI actor model on top of a system that was already designed to receive it.

---

## Phase 1: Foundation

### Repository Structure

```
sentinel/
├── apps/
│   ├── backend/     # Django REST API
│   ├── frontend/    # Next.js 15 dashboard
│   └── worker/      # Celery task queue
├── infra/           # Docker, Nginx, Prometheus, Grafana, OTel
└── docs/            # Architecture, ADRs, roadmap, posts
```

Monorepo. The event schema, API contracts, and TypeScript response types are shared between frontend and backend. An atomic commit can change a Django serializer and the corresponding TypeScript type in the same PR, verified by a single CI run. Polyrepos introduce coordination overhead that is not worth it at this stage.

### Why Django Over FastAPI

Sentinel is a security platform. Django's default posture is security-first: CSRF protection, XSS filtering, SQL injection prevention, argon2 password hashing, and a mature admin interface — all on by default. FastAPI ships with none of these.

We're not optimizing for maximum async throughput. We're optimizing for correctness, security defaults, and a rich ecosystem of security-relevant libraries. The throughput ceiling of synchronous Django is far above what Phase 1 needs, and when it matters, Celery workers and Kafka consumers absorb the load.

### Observability From Day One

The biggest infrastructure decision in Phase 1 was OpenTelemetry *before* any business logic exists. Every HTTP request gets a `trace_id` and `request_id` injected at middleware level, propagated through every log line, database query span, and Celery task.

Three middleware layers handle this in sequence:

```python
class RequestIDMiddleware:
    """Injects UUID into every request. Returns it in X-Request-ID header."""
    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response

class TraceContextMiddleware:
    """Binds the OTel trace_id to structlog so every log includes it."""
    def __call__(self, request):
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            structlog.contextvars.bind_contextvars(
                trace_id=format(span_context.trace_id, "032x"),
            )
        return self.get_response(request)
```

Why this matters for AI systems: when an AI agent makes a bad API call, the investigation needs to trace that exact request through every service it touched. A `request_id` in the response header means the AI client can log which request triggered which behavior. A `trace_id` means engineers can pull the complete distributed trace — every database query, cache hit, and downstream call — for that exact request.

All logs are structured JSON with consistent fields. No regex parsing to query logs.

### The Service/Repository Pattern

Views are thin. No business logic. No database queries.

```
HTTP Request → View (validate + call) → Service (logic) → Repository (DB) → PostgreSQL
```

This is the architecture that makes the risk engine possible in Phase 3. `AuditEventService.list()` is callable from a view, a Celery task, a management command, or the risk scoring engine — because it has no HTTP dependency. If the logic lived in views, none of those callers could reach it without an HTTP request.

### Health Endpoints

Three endpoints, deliberately separated:

- `GET /health/live/` — is this process running? Never checks dependencies. Kubernetes restarts on failure.
- `GET /health/ready/` — can this serve traffic? Checks PostgreSQL and Redis. Returns 503 if either is down.
- `GET /health/` — full summary with latency per component. For Grafana and engineers.

The separation matters operationally. If Redis goes down, we want requests routed to other instances — not pods restarted (which won't fix Redis). Conflating liveness and readiness is a common operational mistake.

---

## Phase 2: Identity & Audit Ledger

### Custom User Model

`AbstractBaseUser` over `AbstractUser`. Django's `AbstractUser` carries `username`, `first_name`, `last_name`, and a groups/permissions M2M setup we don't need. We want:

- `email` as the login identifier
- `role` as a direct DB column (not Django groups)
- Security fields: `last_login_ip`, `failed_login_count`, `must_change_password`

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

In Phase 3, AI agents get their own identity model — not shoehorned into `SentinelUser`. The user model is for humans. AI agents are identified by API keys with `agent_name` and `model_version` metadata. This distinction is intentional and important for attribution.

### JWT with Redis Blacklisting

`djangorestframework-simplejwt` handles token generation. The non-obvious decision is where to store blacklisted tokens.

simplejwt ships with a database-backed blacklist. Every authenticated request would require a `SELECT` on the outstanding tokens table. That's a DB hit on your hottest path for every API call.

We blacklist JTIs in Redis instead:

```python
_BLACKLIST_PREFIX = "sentinel:jwt:blacklist:"

def _blacklist_jti(jti: str, ttl_seconds: int) -> None:
    cache.set(f"{_BLACKLIST_PREFIX}{jti}", "1", timeout=ttl_seconds)

def _is_blacklisted(jti: str) -> bool:
    return cache.get(f"{_BLACKLIST_PREFIX}{jti}") is not None
```

O(1) lookup. TTL set to match refresh token lifetime — keys auto-expire. No cleanup job. No additional DB load.

Refresh token rotation is implemented manually in `AuthService`. Every refresh:
1. Validates the submitted token
2. Checks it against Redis blacklist
3. If clean: blacklists the consumed JTI immediately
4. Issues a fresh pair

Stolen refresh token reuse is detected on the next legitimate refresh attempt.

### RBAC Without Django Groups

Four roles on a `CharField`. Role embedded in JWT payload at issuance:

```python
class IsAuditorOrAbove(BasePermission):
    _allowed = {Role.ADMIN, Role.AUDITOR}

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role in self._allowed
        )
```

Role check = zero database queries. The information is in the token.

### The Immutable Audit Ledger

The audit event model is the foundation of the entire platform. Every action — by every actor — produces one.

```python
class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # WHO acted — denormalized snapshots, not foreign keys
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_email = models.EmailField(blank=True, default="")
    actor_role = models.CharField(max_length=20, blank=True, default="")
    actor_ip = models.GenericIPAddressField(null=True, blank=True)
    # Phase 3 adds: actor_type (HUMAN | SERVICE | AI_AGENT) and agent_name

    # WHAT happened
    event_type = models.CharField(max_length=64, choices=AuditEventType.choices)

    # WHAT was affected
    resource_type = models.CharField(max_length=64, blank=True, default="")
    resource_id = models.CharField(max_length=128, blank=True, default="")

    # CONTEXT
    metadata = models.JSONField(default=dict)
    request_id = models.CharField(max_length=64, blank=True, default="")

    # TAMPER EVIDENCE
    signature = models.CharField(max_length=64, blank=True, default="")

    # WHEN — future partition key (range by month)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # No updated_at — append-only by design
```

Note the denormalized actor fields. We store email and role *at the time of the event* — not a foreign key. User records change. Audit records must accurately reflect the state *when the action occurred*. If an AI agent's configuration changes after an event, the audit record still shows what it was.

Phase 3 extends this with `actor_type` and AI-agent-specific fields. The schema is designed to receive them without migration pain.

### Three-Layer Immutability

**Layer 1: Repository.** `AuditEventRepository.update()` and `.delete()` raise `NotImplementedError` unconditionally. Application code physically cannot call them.

**Layer 2: Django admin.** `has_change_permission` and `has_delete_permission` return `False`. The admin interface shows records but cannot modify them.

**Layer 3: HMAC-SHA256 signatures.** Even if someone modifies the record directly at the database level (bypassing both the application and admin), the signature will not match on verification.

```python
def compute_event_signature(event_id, event_type, actor_id, actor_email,
                             created_at, metadata, secret_key):
    # Hash metadata for efficient signing of large payloads
    payload_hash = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, default=str).encode()
    ).hexdigest()

    message = "|".join([
        str(event_id), event_type,
        str(actor_id) if actor_id else "",
        actor_email, created_at.isoformat(), payload_hash,
    ])

    return hmac.new(
        key=secret_key.encode(),
        msg=message.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
```

JSON sorted before hashing — key insertion order doesn't affect the signature. `hmac.compare_digest` for constant-time comparison — no timing attacks.

`GET /api/v1/events/{id}/verify/` recomputes and compares. A tampered record fails instantly.

### The @audit_action Decorator

The practical problem with audit logging: engineers forget. The `@audit_action` decorator makes forgetting structurally impossible:

```python
class RegisterView(APIView):
    @audit_action(
        event_type="USER_CREATED",
        resource_type="user",
        get_resource_id=lambda req, resp: resp.data.get("id"),
    )
    def post(self, request):
        # Register the user...
        return Response(user_data, status=201)
```

Fires after a successful 2xx response. Dispatches a Celery task with `acks_late=True` — no audit record lost on worker crash. Three retries with five-second backoff. Synchronous mode available where regulations demand immediate write.

---

## Current API Surface

```
POST   /api/v1/auth/register/         Create account
POST   /api/v1/auth/login/            Obtain JWT pair
POST   /api/v1/auth/refresh/          Rotate refresh token
POST   /api/v1/auth/logout/           Blacklist refresh token
GET    /api/v1/auth/me/               Current user profile
POST   /api/v1/auth/me/password/      Change password

POST   /api/v1/events/ingest/         Record an audit event
GET    /api/v1/events/                List events (cursor-paginated, filtered)
GET    /api/v1/events/{id}/           Retrieve single event
GET    /api/v1/events/{id}/verify/    Verify HMAC signature integrity

GET    /health/live/                  Liveness probe
GET    /health/ready/                 Readiness probe
GET    /health/                       Full health summary
```

---

## What Phase 3 Adds

Phase 3 introduces the risk intelligence engine and the AI actor model.

Every audit event gets a risk score. AI agents get dedicated identities — named, versioned, scoped. The risk engine builds behavioral baselines per actor type. An AI agent that suddenly accesses 10× its normal data volume triggers an alert within seconds.

The audit ledger we built in Phase 2 is the input. Every event we now record cleanly becomes a signal the risk engine scores in real time.

Next post: **"How Do You Audit What an AI Agent Does?"** — the problem Phase 3 solves, followed by the technical deep-dive on the risk engine itself.

---

*Star the repo: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*

*v0.2.0 tagged. Phase 3 in progress.*
