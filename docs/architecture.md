# Sentinel Architecture

## Overview

Sentinel is a platform, not a microservice. It is structured as a monorepo containing three runtime components:

- `apps/backend` — Django REST API and domain logic
- `apps/frontend` — Next.js dashboard (App Router)
- `apps/worker` — Celery worker process

These components communicate through well-defined interfaces: the REST API (HTTP), the task queue (Redis/Kafka), and the database (PostgreSQL).

---

## Request Lifecycle

```
Client Request
    │
    ▼
Nginx (reverse proxy, TLS termination, rate limiting)
    │
    ▼
Django Application Server (Gunicorn)
    │
    ▼
┌─────────────────────────────────┐
│        Middleware Stack          │
│  1. SecurityHeadersMiddleware    │
│  2. RequestIDMiddleware          │  ← injects X-Request-ID
│  3. TraceContextMiddleware       │  ← W3C traceparent propagation
│  4. StructuredLoggingMiddleware  │  ← attaches request context to logs
│  5. RateLimitMiddleware          │  ← per-IP and per-key limits
└─────────────────────────────────┘
    │
    ▼
URL Router → api/v1/ namespace
    │
    ▼
View (request validation, authentication check)
    │
    ▼
Service Layer (business logic, orchestration)
    │
    ├──► Repository Layer (database access via ORM)
    │         │
    │         ▼
    │    PostgreSQL
    │
    ├──► Cache Layer (Redis)
    │
    └──► Task Queue (Celery → Redis → Worker)
              │
              ▼
         Celery Worker (async processing)
```

---

## Database Architecture

### PostgreSQL Design Principles

**Schema design:**
- UUID primary keys on all tables (non-enumerable, distributed-safe)
- `created_at` and `updated_at` on all models via `TimestampedModel` base class
- `deleted_at` on soft-deletable models (no hard deletes on audit-relevant data)
- No raw SQL in application code — ORM only, with `select_related`/`prefetch_related` to prevent N+1

**Audit table (Phase 2+):**
- Append-only at the application layer (no UPDATE, no DELETE)
- `created_at` designed as the future partition key (range partitioning by month)
- Separate tablespace consideration for retention policies

**Connection management:**
- PgBouncer in transaction mode for connection pooling in production
- `CONN_MAX_AGE=0` in Docker development (connections are cheap at dev scale)
- Separate read replica connection string for reporting queries (Phase 4+)

### Redis Architecture

Redis serves three distinct roles in Sentinel:

| Role | Redis DB | Purpose |
|---|---|---|
| Cache | DB 0 | API response caching, session data |
| Celery Broker | DB 1 | Task queues |
| Celery Results | DB 2 | Task result storage |
| Rate Limiting | DB 3 | Sliding window counters |

Separation by DB index ensures rate limiting never competes with task queue memory.

---

## Service Layer Architecture

All business logic lives in service classes. Services are plain Python classes — no HTTP awareness, no Django views imports.

```python
# Example service interface (not final implementation)
class AuditEventService:
    def __init__(self, repository: AuditEventRepository):
        self._repo = repository

    def record_event(self, payload: AuditEventCreate) -> AuditEvent:
        """Record an immutable audit event."""
        ...

    def get_events_for_actor(
        self,
        actor_id: UUID,
        *,
        from_dt: datetime,
        to_dt: datetime,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Retrieve audit events for a specific actor in a time window."""
        ...
```

Services are instantiated via dependency injection in views:

```python
class AuditEventListView(APIView):
    def __init__(self, service: AuditEventService = None, **kwargs):
        super().__init__(**kwargs)
        self.service = service or AuditEventService(AuditEventRepository())
```

This makes services fully testable with mock repositories.

---

## Observability Architecture

### Three Pillars

**Metrics (Prometheus)**
- `django_http_requests_total` — Request count by method, path, status
- `django_http_request_duration_seconds` — Latency histogram by endpoint
- `celery_task_received_total` — Task throughput
- `celery_task_duration_seconds` — Task execution latency
- `sentinel_audit_events_total` — Business metric: events recorded (Phase 2)
- `sentinel_risk_score_histogram` — Risk score distribution (Phase 3)

**Traces (OpenTelemetry → Jaeger/Tempo)**
- Every HTTP request produces a trace with spans for:
  - View execution
  - Database queries (auto-instrumented via `opentelemetry-instrumentation-django`)
  - Cache operations (auto-instrumented via `opentelemetry-instrumentation-redis`)
  - Celery task dispatch and execution

**Logs (Structured JSON → stdout → log aggregator)**
- All log lines are JSON
- Every log line includes: `trace_id`, `span_id`, `request_id`, `level`, `timestamp`, `logger`, `message`
- No log lines without context in production

### Request IDs

Every request gets a UUID assigned at the `RequestIDMiddleware` level:
- Returned in `X-Request-ID` response header
- Logged with every log line for the request lifecycle
- Included in error responses so clients can reference it in support tickets

---

## Security Architecture

### Defense in Depth

Sentinel implements security at every layer:

| Layer | Control |
|---|---|
| Network | Nginx rate limiting, TLS, no direct port exposure |
| Application | Django security middleware, CORS policy, CSP headers |
| Authentication | JWT (Phase 2) — `djangorestframework-simplejwt` with rotation |
| Authorization | RBAC via Django permissions + `django-guardian` (Phase 2) |
| API Keys | Hashed storage, prefix-based lookup, rotation support (Phase 3) |
| Data | Input validation at serializer layer, parameterized queries only |
| Secrets | Environment variables only, never in code or logs |
| Audit | All mutating actions produce immutable audit records (Phase 2) |

### Security Headers

All responses include:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: [context-specific]
Permissions-Policy: geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

---

## Deployment Architecture

### Local Development (Docker Compose)

```
docker compose up
└── nginx:80          → reverse proxy
└── backend:8000      → Django (Gunicorn)
└── frontend:3000     → Next.js dev server
└── worker            → Celery worker
└── beat              → Celery beat scheduler
└── flower:5555       → Celery monitoring
└── postgres:5432     → PostgreSQL
└── redis:6379        → Redis
└── prometheus:9090   → Metrics scraping
└── grafana:3001      → Dashboards
```

### Production (Phase 4+)

Production deployment targets Kubernetes with:
- Horizontal Pod Autoscaler on API and worker pods
- PgBouncer sidecar for connection pooling
- Redis Sentinel for HA
- Kafka cluster (3 brokers, 3 ZooKeeper nodes)
- Separate Prometheus + Thanos for long-term metric storage

---

## Phase Roadmap Summary

| Phase | Focus | Key Deliverables |
|---|---|---|
| 1 (Current) | Foundation | Repo structure, Docker, CI, health endpoints, OTEL, base API |
| 2 | Identity & Audit | JWT auth, RBAC, immutable audit ledger, Kafka integration |
| 3 | Risk & Alerting | Risk scoring engine, alert rules, API key management, webhooks |
| 4 | Dashboard | Next.js dashboard, compliance reports, investigation tools |
| 5 | Scale & Multi-tenancy | Tenant isolation, horizontal scaling, SLA monitoring |
