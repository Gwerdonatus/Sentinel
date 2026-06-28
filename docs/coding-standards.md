# Sentinel Coding Standards

All contributors must follow these standards. CI enforces them automatically.

---

## Python

### Toolchain

| Tool | Purpose | Config |
|---|---|---|
| `ruff` | Linting + formatting | `pyproject.toml` |
| `mypy` | Static type checking | `pyproject.toml` |
| `pytest` | Testing | `pyproject.toml` |
| `coverage` | Coverage reporting | `pyproject.toml` |

### Type Hints

All functions and methods must have complete type hints. No `Any` without a comment explaining why.

```python
# ✅ Correct
def compute_risk_score(event: AuditEvent, *, baseline: float = 0.0) -> RiskScore:
    ...

# ❌ Wrong
def compute_risk_score(event, baseline=0.0):
    ...
```

### Naming

- Classes: `PascalCase` (`AuditEventService`)
- Functions and methods: `snake_case` (`record_event`)
- Constants: `SCREAMING_SNAKE_CASE` (`MAX_RETRY_ATTEMPTS`)
- Private attributes: single underscore prefix (`self._repository`)
- Type aliases: `PascalCase` (`AuditEventCreate = TypedDict[...]`)

### Imports

Group imports in this order (enforced by `ruff`):
1. Standard library
2. Third-party (`django`, `rest_framework`, `celery`)
3. Internal (`from sentinel.core import ...`)

No wildcard imports (`from module import *`).

### Django Specifics

**Never put business logic in:**
- Views (thin — validate, call service, return)
- Serializers (serialize/deserialize only, basic field validation)
- Models (queryset helpers are acceptable, business logic is not)

**Always put business logic in:**
- Services (`sentinel/<app>/services.py`)

**Always put database access in:**
- Repositories (`sentinel/<app>/repositories.py`)
- Model managers for complex queryset logic

**Model conventions:**
```python
class AuditEvent(TimestampedModel):
    """Immutable record of a security-relevant action.

    Audit events are append-only. Once created, they cannot be modified
    or deleted at the application layer.
    """

    id: models.UUIDField = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    # ... fields

    class Meta:
        db_table = "audit_events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor_id", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"AuditEvent({self.event_type}, {self.actor_id}, {self.created_at})"
```

**Queryset optimization:**
- Always use `select_related` for ForeignKey traversal in list endpoints
- Always use `prefetch_related` for ManyToMany or reverse FK traversal
- Never call `.count()` in a loop — use aggregation
- Use `.only()` or `.defer()` for large models when returning partial data

### Error Handling

Use Sentinel's exception hierarchy (defined in `sentinel/core/exceptions.py`):

```python
# ✅ Correct — domain exception
raise SentinelValidationError("Actor ID cannot be empty")

# ✅ Correct — explicit not-found
raise SentinelNotFoundError(f"Event {event_id} not found")

# ❌ Wrong — leaks internals, not handled by DRF exception handler
raise ValueError("bad input")
```

Exception handler in `core/` converts all `SentinelException` subclasses to appropriate HTTP responses automatically.

### Logging

Use structured logging only:

```python
import logging
logger = logging.getLogger(__name__)

# ✅ Correct — structured key-value pairs
logger.info("Audit event recorded", extra={
    "event_id": str(event.id),
    "event_type": event.event_type,
    "actor_id": str(event.actor_id),
})

# ❌ Wrong — unstructured, unsearchable
logger.info(f"Recorded event {event.id} for actor {event.actor_id}")
```

**Never log:**
- Passwords or password hashes
- API keys or secrets (even partial)
- Full JWT tokens
- PII beyond what is operationally necessary

### Testing Standards

Every module must have tests. Minimum coverage: **90%** on new code.

**Test structure:**
```
tests/
├── unit/
│   ├── test_services.py       # Pure function tests, no DB
│   ├── test_repositories.py   # DB tests with pytest-django
│   └── test_serializers.py    # Serializer tests
└── integration/
    ├── test_api_health.py     # Full request/response cycle
    └── test_api_events.py     # Business endpoint tests
```

**Test conventions:**
```python
# Use descriptive test names
def test_audit_event_service_raises_when_actor_id_is_empty() -> None:
    ...

# Use Factory Boy for test fixtures
event = AuditEventFactory(event_type="LOGIN")

# Use pytest fixtures, not setUp/tearDown
@pytest.fixture
def audit_service(db) -> AuditEventService:
    return AuditEventService(repository=AuditEventRepository())

# Test one thing per test function
def test_risk_score_exceeds_threshold_for_impossible_travel() -> None:
    # Arrange
    ...
    # Act
    score = service.compute_risk(event)
    # Assert
    assert score.value > RiskThreshold.HIGH
```

---

## TypeScript (Frontend)

- Strict mode (`"strict": true` in tsconfig)
- No `any` without comment
- All components typed with explicit props interfaces
- Zod for runtime validation of API responses
- Server components by default, client components only when needed
- No inline styles — Tailwind utility classes only

---

## Git

### Commit Messages

Format: `type(scope): description`

```
feat(audit): add immutable event recording endpoint
fix(auth): prevent token reuse after rotation
docs(adr): add ADR-009 for Kafka partition topology
test(risk): add unit tests for impossible travel detection
chore(deps): upgrade Django to 5.1.2
refactor(core): extract request ID generation to utility function
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `perf`, `ci`

### Branch Strategy

```
main              ← always deployable
└── develop       ← integration branch
    ├── feat/...  ← feature branches
    ├── fix/...   ← bug fix branches
    └── chore/... ← maintenance branches
```

PRs target `develop`. `develop` merges to `main` on release.

### PR Requirements

- All CI checks pass
- Minimum one reviewer approval
- Coverage does not decrease
- No new `type: ignore` without comment
- ADR updated if architectural decision is changed
