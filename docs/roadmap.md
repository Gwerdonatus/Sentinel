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

## Phase 3 — Risk Intelligence & AI Actor Tracking

**Goal:** Know when something is wrong before it becomes an incident. Know when AI is behaving anomalously.

**Actor identity model:**
- Extend audit events to carry `actor_type`: `HUMAN | SERVICE | AI_AGENT`
- AI agents identified by dedicated API keys with `agent_name` and `model_version` fields
- Per-actor behavioral profiles — humans and AI agents tracked separately
- Every AI action attributed to a named agent, not just an anonymous service account

**Risk scoring engine:**
- Composite risk score (0–100) on every audit event
- Signals for human actors: impossible travel, unusual hours, new device, velocity spike
- Signals for AI actors: anomalous data volume, out-of-scope resource access, prompt injection indicators, rate spikes
- Baseline behavioral profile per actor, updated on rolling 30-day window
- Risk score stored on the audit event — queryable historically

**Alert rule engine:**
- Rule DSL: `IF risk_score > 80 AND actor_type = AI_AGENT THEN alert`
- Evaluation on every ingested event (Celery task)
- Alert state machine: OPEN → ACKNOWLEDGED → RESOLVED
- Built-in rules: impossible travel, AI data exfiltration pattern, admin action outside business hours

**API Key management:**
- Keys for human API access and AI agent identity
- HMAC-SHA256 hashed storage — plain text never stored
- Per-key scope definitions (read-only, write, admin)
- Rotation with grace period — old key valid for N hours after rotation
- Usage tracking per key — feeds into risk scoring

**Notification engine:**
- Email (SMTP/SendGrid)
- Slack webhook
- PagerDuty
- Outbound webhook delivery with HMAC signature

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
