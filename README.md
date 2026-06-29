# Sentinel

> **The Trust Layer for AI-Powered Financial Systems**

[![CI](https://github.com/Gwerdonatus/Sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/Gwerdonatus/Sentinel/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://github.com/Gwerdonatus/Sentinel)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Django 5.x](https://img.shields.io/badge/django-5.x-green)](https://djangoproject.com)

---

## What Is Sentinel?

Modern financial systems no longer have only human users. They have humans, backend services, mobile apps, third-party APIs, and increasingly — **AI agents** — all interacting with the same infrastructure.

An AI support agent that exports 50,000 customer records because of a bad prompt. An AI model reviewing transactions that starts approving anomalous ones. An MCP server with production access that performs actions nobody authorized. Code written by an AI assistant that accidentally exposes secrets.

The question is no longer *"Can AI help us?"*

It's **"How do we trust what AI and automated systems are doing?"**

Sentinel is the answer. An open-source, event-driven security, audit, and risk intelligence platform that gives financial systems the visibility, auditability, and real-time intelligence needed to operate safely — whether the actor is a human, a service, or an AI agent.

**Sentinel exists to answer:**

- Who or what performed this action — human, service, or AI agent?
- Should this action be trusted given the actor's history and context?
- Can we prove what happened six months later with a tamper-proof record?
- Can we detect an AI agent behaving anomalously in real time?
- Can we reconstruct every action an AI took during an incident?

Sentinel does **not** process money. It is the trust layer between actors — human and AI — and the systems that do.

---

## Core Capabilities

| Capability | Description | Status |
|---|---|---|
| Immutable Audit Ledger | Tamper-evident, HMAC-signed record of every action by every actor | ✅ Phase 2 |
| JWT Auth + RBAC | Email-first auth, role-based access, Redis token blacklist | ✅ Phase 2 |
| Health + Observability | OpenTelemetry traces, Prometheus metrics, structured logging | ✅ Phase 1 |
| Event Streaming (Kafka) | Ordered, durable, replayable event pipeline at scale | 🔜 Phase 3 |
| Risk Intelligence Engine | Real-time behavioral scoring — humans and AI agents alike | 🔜 Phase 3 |
| AI Actor Tracking | Identify, attribute, and audit AI agent actions separately from humans | 🔜 Phase 3 |
| Alert Rule Engine | Condition-based alerts when risk score or behavior crosses threshold | 🔜 Phase 3 |
| API Key Management | Scoped keys with rotation, usage tracking, and per-key audit trail | 🔜 Phase 3 |
| Dashboard | Investigation UI, actor timelines, compliance reports | 🔜 Phase 4 |
| Compliance Reports | PCI-DSS, SOC 2 evidence export with AI action attribution | 🔜 Phase 4 |

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Sentinel Trust Layer                          │
│                                                                       │
│   Actors:  👤 Humans    🤖 AI Agents    ⚙️ Services    📱 Mobile     │
│                │               │              │             │         │
│                └───────────────┴──────────────┴─────────────┘         │
│                                      │                                │
│                           ┌──────────▼──────────┐                    │
│                           │   Django REST API    │                    │
│                           │   JWT Auth + RBAC    │                    │
│                           │   api/v1/ versioned  │                    │
│                           └──────────┬──────────┘                    │
│                                      │                                │
│        ┌─────────────────────────────┼──────────────────┐            │
│        │                             │                  │            │
│  ┌─────▼──────┐   ┌──────────────────▼────┐   ┌────────▼───────┐    │
│  │  Audit     │   │   Risk Intelligence    │   │  PostgreSQL    │    │
│  │  Ledger    │   │   Engine (Phase 3)     │   │  Redis         │    │
│  │  (HMAC)    │   │   Scores every actor   │   │  Celery        │    │
│  └────────────┘   └───────────────────────┘   └────────────────┘    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Observability: OpenTelemetry → Prometheus → Grafana           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

**Backend**
- Python 3.12, Django 5.x, Django REST Framework 3.x
- PostgreSQL 16, Redis 7, Celery 5.x
- Kafka 3.x (Phase 2+)

**Frontend**
- Next.js 15 (App Router), TypeScript 5.x, TailwindCSS 3.x

**Infrastructure**
- Docker + Docker Compose
- GitHub Actions (CI/CD)
- Prometheus + Grafana
- OpenTelemetry
- Nginx

**Testing**
- pytest, Factory Boy, Coverage.py

---

## Quickstart

### Prerequisites

- Docker 24+ and Docker Compose v2
- Make (optional but recommended)
- Node.js 20+ (for frontend local development)

### Start Everything

```bash
git clone https://github.com/your-org/sentinel.git
cd sentinel

# Copy environment files
cp .env.example .env
cp apps/backend/.env.example apps/backend/.env.local
cp apps/frontend/.env.example apps/frontend/.env.local

# Start the full stack
docker compose up --build

# In another terminal — run migrations
docker compose exec backend python manage.py migrate

# Create a superuser (optional)
docker compose exec backend python manage.py createsuperuser
```

**Sentinel is now running:**

| Service | URL |
|---|---|
| API | http://localhost:8000/api/v1/ |
| Health | http://localhost:8000/health/ |
| Admin | http://localhost:8000/admin/ |
| Dashboard | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
| Flower (Celery) | http://localhost:5555 |

---

## Project Structure

```
sentinel/
├── apps/
│   ├── backend/          # Django REST API
│   │   ├── sentinel/     # Django project & apps
│   │   │   ├── api/v1/   # Versioned API endpoints
│   │   │   ├── core/     # Middleware, exceptions, utils
│   │   │   ├── audit/    # Audit ledger (Phase 2)
│   │   │   ├── risk/     # Risk engine (Phase 3)
│   │   │   └── auth_service/ # Auth & RBAC (Phase 2)
│   │   ├── config/       # Django settings
│   │   └── tests/        # Unit & integration tests
│   ├── frontend/         # Next.js dashboard
│   └── worker/           # Celery worker entrypoint
├── infra/
│   ├── docker/           # Dockerfiles
│   ├── nginx/            # Nginx config
│   ├── prometheus/       # Prometheus config
│   └── grafana/          # Grafana dashboards
├── docs/
│   ├── adr/              # Architecture Decision Records
│   ├── architecture.md
│   ├── roadmap.md
│   ├── coding-standards.md
│   ├── contributing.md
│   └── security-policy.md
└── .github/workflows/    # CI/CD pipelines
```

---

## Documentation

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Coding Standards](docs/coding-standards.md)
- [Contributing Guide](docs/contributing.md)
- [Security Policy](docs/security-policy.md)
- [ADR Index](docs/adr/README.md)

---

## Development

```bash
# Run backend tests
docker compose exec backend pytest --cov=sentinel --cov-report=term-missing

# Run frontend dev server
cd apps/frontend && npm run dev

# Lint backend
docker compose exec backend ruff check .

# Format backend
docker compose exec backend ruff format .

# Type check backend
docker compose exec backend mypy sentinel/
```

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Acknowledgements

Sentinel draws on patterns from production systems at Stripe, Plaid, and Monzo. It is designed to be the security infrastructure layer that every fintech company needs but rarely builds well.
