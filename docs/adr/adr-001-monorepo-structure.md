# ADR-001: Monorepo Structure

## Status

Accepted

## Date

2025-01-01

## Context

Sentinel consists of three distinct runtime components: a Django REST API, a Next.js dashboard, and Celery workers. A decision is required on how to structure these components in version control.

Options considered:
1. **Polyrepo** — Each component in its own repository
2. **Monorepo** — All components in a single repository with `apps/` subdivision
3. **Monolith** — All code in a single Django project with no frontend separation

## Decision

Adopt a **monorepo structure** under `apps/`.

```
sentinel/
├── apps/
│   ├── backend/    # Django API
│   ├── frontend/   # Next.js dashboard
│   └── worker/     # Celery entrypoint
├── infra/          # All infrastructure config
└── docs/           # All documentation
```

## Rationale

- **Shared contracts first** — The event schema, error codes, and API types are shared between frontend and backend. A monorepo makes it trivial to co-locate generated TypeScript types from the Django API schema without a separate package publishing step.
- **Atomic changes** — An API breaking change and the corresponding frontend update ship in the same PR and the same CI run. This eliminates the cross-repo coordination cost and the version drift risk that kills polyrepos.
- **Single CI pipeline** — GitHub Actions can run backend tests, frontend tests, and integration tests in a single workflow with proper caching. Polyrepos require workflow synchronization across repositories, which adds significant operational overhead.
- **Operational simplicity at this stage** — Sentinel is not yet at a scale where independent deployment velocity between repos would justify the coordination overhead. Monorepo defers that complexity until it's warranted.

## Consequences

**Positive:**
- One `git clone` gives a complete development environment
- ADRs, contributing guide, and docs cover the entire platform
- Docker Compose starts the full stack
- API contracts and frontend types stay in sync

**Negative:**
- Repository grows in size as the platform matures
- CI pipeline takes longer than a per-component pipeline would
- Developers unfamiliar with the backend cannot easily work on a pure-frontend change without the full repo context

## Mitigation

CI is structured with path-based job filtering — backend jobs only run when `apps/backend/**` changes, frontend jobs only run when `apps/frontend/**` changes. This keeps CI fast despite the monorepo.

## Alternatives Considered

**Polyrepo** was rejected because the coordination cost of keeping API contracts synchronized across repositories is a known reliability failure mode. When the audit event schema changes, every consumer needs to update. A monorepo makes that refactor a single PR.

**Turborepo/Nx** was considered but rejected for Phase 1. These tools add value at 5+ packages. At 3 apps, they add tooling complexity with marginal benefit.
