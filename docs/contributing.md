# Contributing to Sentinel

Thank you for considering contributing to Sentinel. This document outlines the process for contributing code, documentation, and bug reports.

---

## Before You Start

Read:
- [Architecture documentation](architecture.md) — understand the system design
- [Coding standards](coding-standards.md) — understand what we enforce
- [Security policy](security-policy.md) — understand our security requirements
- [ADR index](adr/README.md) — understand the major decisions already made

---

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Gwerdonatus/Sentinel.git
cd Sentinel

# Copy environment files
cp .env.example .env

# Start the full stack
docker compose up -d --build --wait --wait-timeout 300

# Run backend tests
docker compose run --rm --no-deps --user root \
  -e ENVIRONMENT=test -e KAFKA_ENABLED=False -e OTEL_ENABLED=False \
  backend sh -c 'pip install -r requirements-dev.txt && pytest --cov=sentinel'

# Run frontend type check
docker compose exec frontend npm run type-check
```

---

## Contribution Types

### Bug Reports

Use the GitHub issue template. Include:
- Sentinel version (check `GET /api/v1/`)
- Steps to reproduce
- Expected behavior
- Actual behavior
- Relevant logs (redact any sensitive data)

### Feature Requests

Open a discussion before implementing. Features that affect the core event schema, authentication, or RBAC require an ADR before implementation begins.

### Pull Requests

1. Fork the repository
2. Create a branch: `feat/your-feature` or `fix/your-bug`
3. Make your changes
4. Ensure all CI checks pass locally:
   ```bash
   # Backend
   # Use the disposable test container described in the README for Ruff,
   # Django checks and tests; development dependencies are not in runtime images.
   docker compose run --rm --no-deps --user root \
     -e ENVIRONMENT=test -e KAFKA_ENABLED=False -e OTEL_ENABLED=False \
     backend sh -c 'pip install -r requirements-dev.txt && pytest --cov=sentinel'

   # Frontend
   docker compose exec frontend npm run lint
   docker compose exec frontend npm run type-check
   ```
5. Write or update tests (coverage must not decrease)
6. Update documentation if your change affects behavior
7. Submit the PR targeting `main`

---

## Commit Message Format

We follow Conventional Commits:

```
type(scope): short description

Optional longer body.

Closes #123
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `ci`

Scopes: `core`, `audit`, `risk`, `auth`, `api`, `worker`, `frontend`, `infra`, `docs`

---

## Code Review Standards

All PRs require:
- At least one approval from a maintainer
- All CI checks passing
- No reduction in test coverage
- No new `# type: ignore` without a comment explaining why
- ADR updated if an architectural decision is changed

---

## Architecture Changes

Any change that:
- Adds a new service or external dependency
- Changes the database schema in a breaking way
- Changes the API contract in a non-backward-compatible way
- Changes the authentication or authorization model

...requires an ADR submitted before implementation and merged before the PR.

---

## Security Issues

**Do not open public issues for security vulnerabilities.** See [security policy](security-policy.md).

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
