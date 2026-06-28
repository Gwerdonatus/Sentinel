# ADR-002: Django Over FastAPI

## Status

Accepted

## Date

2025-01-01

## Context

The backend API must be implemented in Python. Two mature options exist: Django (with Django REST Framework) and FastAPI.

## Decision

Use **Django 5.x with Django REST Framework 3.x**.

## Rationale

Sentinel's requirements tilt strongly toward Django:

**Security primitives** — Django ships with CSRF protection, clickjacking headers, SQL injection prevention, XSS filtering, and secure password hashing as defaults. FastAPI ships with none of these. For a security platform, starting from a secure default baseline is not optional.

**ORM + migrations** — Django's ORM and migration system are mature and battle-tested at scale. The audit ledger will have complex schema evolution requirements. Django migrations handle multi-step schema changes with rollback support; FastAPI typically uses Alembic which requires more manual configuration.

**Admin interface** — Django Admin provides a production-quality backoffice for Sentinel's internal operations out of the box. This is particularly valuable for managing API keys, reviewing flagged events, and operating the risk engine during early deployment.

**Ecosystem relevance** — Libraries directly applicable to Sentinel's security mission:
  - `django-axes` — Brute force protection
  - `django-guardian` — Object-level permissions  
  - `django-ratelimit` — View-level rate limiting
  - `django-auditlog` — Reference implementation patterns
  - `django-csp` — Content Security Policy headers
  - `djangorestframework-simplejwt` — JWT with rotation

**Async support** — Django 5.x supports async views natively. For endpoints that do not require it, synchronous Django performs comparably to async FastAPI in practice at this scale.

## Consequences

**Positive:**
- Security defaults are on by default, not opt-in
- Admin interface for free
- Mature migration tooling
- Rich security-focused ecosystem
- Team hiring pool for Django is larger than FastAPI

**Negative:**
- Heavier than FastAPI for pure-throughput endpoints
- Async adoption is more complex than FastAPI's native async-first model
- More boilerplate for simple CRUD endpoints

## Trade-off Accepted

Sentinel's primary constraint is **correctness and security**, not maximum throughput. A financial security platform that processes millions of events should not optimize for raw RPS at the cost of security defaults. If throughput becomes a bottleneck, Celery workers and Kafka consumers will absorb the load — not a switch to FastAPI.

## Alternatives Considered

**FastAPI** was seriously evaluated. It is superior for:
- Maximum async throughput
- Auto-generated OpenAPI schemas
- Simple dependency injection

It was rejected because the lack of security defaults and the thinner ecosystem around auth, permissions, and audit functionality means Sentinel would spend significant engineering effort rebuilding what Django provides.
