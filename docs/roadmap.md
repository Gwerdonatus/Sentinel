# Sentinel Roadmap

## Positioning

Sentinel is security infrastructure for the AI era of financial systems.

Modern financial systems have multiple actor types interacting with the same infrastructure: human users, backend services, mobile clients, third-party APIs, and increasingly AI agents — support bots, transaction reviewers, code assistants with production access, MCP servers.

Every phase of Sentinel is built with this reality in mind. The audit ledger records *who* acted — human or AI. The risk engine scores *what* changed — whether the actor is a person or an automated system. The dashboard shows timelines across all actor types so investigators can reconstruct exactly what happened.

---

## Phase 1 — Foundation ✅ Complete

**Goal:** Production-grade infrastructure that every subsequent phase builds on without structural refactoring.

- Monorepo structure (apps/backend, apps/frontend, infra/, docs/)
- Django 5.x + DRF + Celery + Redis + PostgreSQL
- Next.js 15 App Router frontend
- OpenTelemetry instrumentation from day one
- Request ID + W3C trace context middleware
- Structured JSON logging (structlog)
- Cursor-based pagination
- Health endpoints (liveness, readiness, summary)
- Docker Compose full stack
- GitHub Actions CI
- 8 Architecture Decision Records

---

## Phase 2 — Identity & Audit Ledger ✅ Complete

**Goal:** Prove what happened, by whom — human or AI.

- Custom SentinelUser model (email-first, RBAC roles)
- JWT authentication with Redis blacklist (O(1), TTL-based)
- Refresh token rotation — stolen token reuse detection
- RBAC: ADMIN / AUDITOR / ANALYST / VIEWER
- Immutable AuditEvent model — append-only, no UPDATE/DELETE
- HMAC-SHA256 event signatures — tamper detection at DB level
- Three-layer immutability enforcement
- `@audit_action` decorator — automatic audit recording on views
- Async event recording via Celery (acks_late=True, 3 retries)
- Signature verification endpoint
- ADRs 009-011

---

## Phase 3 — Risk Intelligence & AI Actor Tracking ✅ Complete

**Goal:** Know when something is wrong before it becomes an incident. Know when AI is behaving anomalously.

**Actor identity model:**
- `actor_type` field on AuditEvent: `HUMAN | SERVICE | AI_AGENT`
- `agent_name` and `risk_score` added via non-breaking migration
- AI agents identified by dedicated API keys with `agent_name`, `agent_version`, `agent_description`
- Every AI action attributed to a named agent, not an anonymous service account

**Risk scoring engine:**
- Composite risk score (0–100) on every audit event, computed async via Celery
- Human signals: impossible travel (IP subnet heuristic), velocity spike (log-scale baseline comparison), off-hours admin action
- AI signals: data volume anomaly (10x baseline = exfiltration pattern), new resource type access (scope creep detection)
- Dominant-signal + secondary-boost scoring algorithm (primary signal drives score, up to +15 from secondary signals)
- All signals fail open (never crash the pipeline, return 0 on error)

**Alert rule engine:**
- Structured JSON conditions (AND/OR composition, 9 operators) — no eval(), no custom DSL parser
- 5 built-in rules seeded via migration: critical score, high-risk AI agent, impossible travel, off-hours admin, AI new resource type
- Duplicate suppression window per rule+actor
- Alert lifecycle: OPEN → ACKNOWLEDGED → RESOLVED

**API Key management:**
- `sk_live_`/`sk_test_` key format, HMAC-SHA256 hashed storage, prefix-based O(1) lookup
- Scoped permissions (`events:write`, `alerts:read`, etc.)
- Rotation with configurable grace period
- Usage tracking feeds risk velocity signals
- Custom DRF authentication backend — Bearer token auth alongside JWT

**Notification engine:**
- Slack webhook, email (Django backend), outbound webhook (HMAC-signed)
- Independent Celery task per channel — one failure doesn't block others
- Delivery outcome tracked on the Alert record

**New endpoints:**
```
GET    /api/v1/alerts/                       List alerts (filtered, paginated)
GET    /api/v1/alerts/{id}/                  Alert detail
POST   /api/v1/alerts/{id}/acknowledge/      Acknowledge
POST   /api/v1/alerts/{id}/resolve/          Resolve
GET    /api/v1/alerts/rules/                 List rules
POST   /api/v1/alerts/rules/                 Create rule
DELETE /api/v1/alerts/rules/{id}/            Deactivate rule
GET    /api/v1/risk/summary/                 Platform risk summary
GET    /api/v1/risk/actors/{actor_id}/       Actor risk profile
GET    /api/v1/api-keys/                     List keys
POST   /api/v1/api-keys/create/              Create key (AI agent or service)
GET    /api/v1/api-keys/{id}/                Key detail
DELETE /api/v1/api-keys/{id}/                Revoke key
```

- ADRs 012-014: actor_type denormalization, JSON conditions over DSL, risk_score immutability exception
- 4 new test files: risk engine, evaluator, API keys, integration coverage for alerts/keys

---

## Phase 4 — Dashboard & Compliance

**Goal:** The operational surface for security teams and compliance officers.

- Next.js dashboard (React Server Components for large audit tables)
- Actor timeline view — reconstruct any human or AI session end-to-end
- Risk score timeline per actor
- Alert management inbox
- AI agent activity summary — what did each AI agent do today/this week?
- Compliance reports:
  - PCI-DSS event export with AI action attribution
  - SOC 2 evidence package
  - Custom date range export (CSV, JSON, PDF)
- Investigation tools:
  - Cross-event correlation by session, device, IP, or AI agent
  - Export investigation case

---

## Phase 5 — Scale & Multi-tenancy

**Goal:** Deploy Sentinel as a shared platform across multiple organizations.

- Tenant isolation (row-level security in PostgreSQL)
- Per-tenant Kafka topics
- Per-tenant rate limits and risk thresholds
- Kubernetes deployment manifests with HPA
- Multi-region event replication
- SLA monitoring (P99 ingestion latency)
- Tenant billing and usage metering
- SDK: Python client for easy event ingestion from any service

---

## Content Roadmap (parallel to engineering)

Each phase publishes two posts:

| Phase | Post 1 (Problem) | Post 2 (Technical) |
|---|---|---|
| 1+2 | The security problem every fintech ignores | Building the foundation and audit ledger |
| 3 | How do you audit what an AI agent does? | Building real-time risk intelligence |
| 4 | Why AI actions need immutable trails | Building the investigation dashboard |
| 5 | Security infrastructure for AI-native fintechs | Scaling to multi-tenant |
