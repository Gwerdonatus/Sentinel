# Sentinel

> **Event-Driven Security, Audit & Risk Intelligence Platform for Financial Systems**

[![CI](https://github.com/your-org/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/sentinel/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen)](https://github.com/your-org/sentinel)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Django 5.x](https://img.shields.io/badge/django-5.x-green)](https://djangoproject.com)

---

## What Is Sentinel?

Sentinel is the infrastructure layer that protects modern financial systems.

Modern fintech companies receive millions of events every day — logins, transfers, admin approvals, API calls, device registrations. Most systems simply execute these actions.

**Sentinel exists to answer:**

- Who performed this action?
- Should this action be trusted?
- Can we prove what happened six months later?
- Can suspicious activity be detected immediately?
- Can we investigate incidents in minutes, not days?

Sentinel does **not** process money. It protects systems that do.

---

## Core Capabilities

| Capability | Status |
|---|---|
| Immutable Audit Ledger | 🔜 Phase 2 |
| Event Streaming (Kafka) | 🔜 Phase 2 |
| Risk Intelligence Engine | 🔜 Phase 3 |
| API Key Management | 🔜 Phase 3 |
| JWT Authentication + RBAC | 🔜 Phase 2 |
| Security Alerts | 🔜 Phase 3 |
| Dashboard | 🔜 Phase 4 |
| Prometheus Metrics | ✅ Phase 1 |
| Distributed Tracing (OTEL) | ✅ Phase 1 |
| Health Endpoints | ✅ Phase 1 |
| Webhook Processing | 🔜 Phase 3 |
| Compliance Reports | 🔜 Phase 4 |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Sentinel Platform                        │
│                                                                  │
│  ┌──────────────────┐    ┌──────────────────────────────────┐   │
│  │   Next.js        │    │         Django REST API           │   │
│  │   Dashboard      │◄──►│  api/v1/ (versioned endpoints)   │   │
│  │   (App Router)   │    │                                  │   │
│  └──────────────────┘    └──────────────┬───────────────────┘   │
│                                         │                        │
│              ┌──────────────────────────┼───────────────────┐   │
│              │                          │                    │   │
│   ┌──────────▼──────────┐   ┌──────────▼──────┐   ┌───────▼─┐  │
│   │   Celery Workers     │   │   PostgreSQL     │   │  Redis  │  │
│   │   (Task Queue)       │   │   (Primary DB)   │   │(Cache/  │  │
│   │                     │   │                  │   │ Queue)  │  │
│   └─────────────────────┘   └──────────────────┘   └─────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  Observability Stack                                      │  │
│   │  OpenTelemetry → Prometheus → Grafana                     │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
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
