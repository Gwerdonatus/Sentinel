# Architecture Decision Records

This directory contains all Architecture Decision Records (ADRs) for Sentinel.

An ADR captures an important architectural decision made along with its context and consequences.

## Index

| ADR | Title | Status |
|---|---|---|
| [ADR-001](adr-001-monorepo-structure.md) | Monorepo Structure | Accepted |
| [ADR-002](adr-002-django-over-fastapi.md) | Django Over FastAPI | Accepted |
| [ADR-003](adr-003-celery-before-kafka.md) | Celery Before Kafka | Accepted |
| [ADR-004](adr-004-postgres-partitioning-strategy.md) | PostgreSQL Partitioning Strategy | Accepted |
| [ADR-005](adr-005-uuid-primary-keys.md) | UUID Primary Keys | Accepted |
| [ADR-006](adr-006-opentelemetry-first.md) | OpenTelemetry From Day One | Accepted |
| [ADR-007](adr-007-service-repository-pattern.md) | Service + Repository Pattern | Accepted |
| [ADR-008](adr-008-api-versioning.md) | API Versioning Strategy | Accepted |

## Template

```markdown
# ADR-XXX: Title

## Status

Proposed | Accepted | Deprecated | Superseded by ADR-XXX

## Date

YYYY-MM-DD

## Context

What situation drove this decision?

## Decision

What decision was made?

## Rationale

Why was this the best option?

## Consequences

What are the trade-offs?

## Alternatives Considered

What else was evaluated?
```

| [ADR-009](adr-009-custom-user-model.md) | Custom AbstractBaseUser | Accepted |
| [ADR-010](adr-010-redis-jwt-blacklist.md) | Redis JWT Blacklist Over DB | Accepted |
| [ADR-011](adr-011-hmac-audit-signing.md) | HMAC-SHA256 Audit Signatures | Accepted |
| [ADR-012](adr-012-to-014.md#adr-012-actor_type-as-a-denormalized-field-on-auditevent) | actor_type Denormalized on AuditEvent | Accepted |
| [ADR-013](adr-012-to-014.md#adr-013-structured-json-conditions-over-a-custom-rule-dsl) | Structured JSON Alert Conditions | Accepted |
| [ADR-014](adr-012-to-014.md#adr-014-risk-score-persisted-via-direct-update-bypassing-the-immutability-guard) | Risk Score Update Exception | Accepted |
