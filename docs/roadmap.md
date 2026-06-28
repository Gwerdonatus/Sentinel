# Sentinel Roadmap

## Phase 1 — Foundation (Current)

**Goal:** Production-grade infrastructure that every subsequent phase builds on without structural refactoring.

**Deliverables:**
- [x] Monorepo structure
- [x] Docker + Docker Compose (full local stack)
- [x] GitHub Actions CI (lint, type check, test, coverage)
- [x] Base Django project with production settings pattern
- [x] Base Next.js project (App Router)
- [x] OpenTelemetry instrumentation (traces from day one)
- [x] Prometheus metrics endpoint
- [x] Structured JSON logging
- [x] Request ID middleware
- [x] Health check endpoints (liveness + readiness)
- [x] Nginx reverse proxy
- [x] Architecture documentation
- [x] ADRs (001–008)
- [x] Coding standards
- [x] Security policy
- [x] Contributing guide
- [x] Environment configuration pattern

---

## Phase 2 — Identity & Audit Ledger

**Goal:** The core security primitive — prove what happened and by whom.

**Deliverables:**
- [ ] JWT authentication (`djangorestframework-simplejwt`)
  - Access token (15 minutes)
  - Refresh token (7 days, rotated on use)
  - Token blacklist on logout
- [ ] RBAC with roles: `ADMIN`, `AUDITOR`, `ANALYST`, `VIEWER`
- [ ] Immutable audit event model
  - Append-only at application layer
  - Signed event envelope (HMAC)
  - Event schema v1 definition
- [ ] Kafka integration
  - Producer: Django → Kafka on event
  - Consumer: Celery worker → PostgreSQL
  - Schema registry (Confluent / Redpanda)
- [ ] Audit event API
  - `POST /api/v1/events/` — ingest event
  - `GET /api/v1/events/` — list with filters
  - `GET /api/v1/events/{id}/` — event detail
- [ ] Event search with filters: actor, type, resource, time range
- [ ] User management API
- [ ] Password reset flow
- [ ] Device registration tracking

---

## Phase 3 — Risk Intelligence & Alerting

**Goal:** Real-time detection of suspicious activity.

**Deliverables:**
- [ ] Risk scoring engine
  - Baseline behavioral profile per actor
  - Anomaly detection signals: impossible travel, unusual hours, new device, velocity spike
  - Composite risk score (0–100)
  - Risk score stored with every event
- [ ] Alert rule engine
  - Rule DSL: `IF risk_score > 80 AND event_type IN ['TRANSFER', 'WITHDRAWAL'] THEN alert`
  - Rule evaluation on every event (Celery task)
  - Alert state machine: `OPEN → ACKNOWLEDGED → RESOLVED`
- [ ] API Key management
  - Key creation with permission scopes
  - HMAC-SHA256 hashed storage
  - Key rotation with grace period
  - Usage tracking per key
- [ ] Webhook processing
  - Incoming webhook ingestion
  - Delivery tracking with retry
  - HMAC signature verification for sources
- [ ] Notification engine
  - Email (SMTP/SendGrid)
  - Slack
  - PagerDuty
  - Webhook delivery

---

## Phase 4 — Dashboard & Compliance

**Goal:** The operational surface for security teams.

**Deliverables:**
- [ ] Next.js dashboard
  - Audit log viewer (infinite scroll, real-time updates)
  - Risk score timeline per actor
  - Alert management inbox
  - API key management UI
  - User and role management
- [ ] Compliance reports
  - PCI-DSS event export
  - SOC 2 evidence package
  - Custom date range export (CSV, JSON)
- [ ] Investigation tools
  - Actor timeline view
  - Event correlation (same session, same device)
  - Export case to PDF

---

## Phase 5 — Scale & Multi-tenancy

**Goal:** Deploy Sentinel as a shared platform across multiple organizations.

**Deliverables:**
- [ ] Tenant isolation
  - Row-level security in PostgreSQL
  - Per-tenant Kafka topics
  - Per-tenant rate limits
- [ ] Kubernetes deployment manifests
- [ ] Horizontal scaling of API and worker pods
- [ ] Multi-region event replication
- [ ] SLA monitoring (P99 ingestion latency)
- [ ] Tenant billing and usage metering
