# Local verification — 9 October 2026

Environment: Apple Silicon Mac, Docker Desktop, repository branch `fix/reliable-audit-pipeline`. This records a local verification session, not a throughput benchmark or production certification.

| Check | Result |
|---|---|
| Complete backend suite | 314 passed; 72.58% statement coverage; 65% minimum satisfied |
| Ruff | Lint passed; all 156 Python files formatted |
| Django system checks | No issues |
| Migration consistency | No changes detected |
| Frontend ESLint | No warnings or errors |
| TypeScript | Passed |
| Next.js production build | Passed; all 18 static pages generated |
| Compose configuration | Valid |
| Stack | 14 services running; all nine configured health checks healthy |
| Readiness endpoints | Django, Next.js, Nginx, Prometheus and Grafana returned HTTP 200 |
| Browser workflow | Demo sign-in; overview, alert details, actor timeline, audit log, agent registry, credentials and reports inspected |
| Report generation | Celery generated a ready PDF with 22 events: 18 AI_AGENT + four HUMAN; two named agents; three high-risk events |

## Report regression

Explicit event ordering caused SQL actor grouping to split by timestamp. Constructing a dictionary from those groups then overwrote repeated actor counts. The fix clears ordering for the grouping query while preserving the event-detail ordering. Regression tests cover distinct timestamps, multiple actor types, agent and event-type totals, high-risk totals and an empty ledger.

## Scope and caveats

- Backend tests run in a disposable container with `ENVIRONMENT=test`, `KAFKA_ENABLED=False` and `OTEL_ENABLED=False`, isolating regression tasks from the live demo broker.
- Production frontend checks use `NODE_ENV=production` and `NEXT_DIST_DIR=.next`; development uses `.next-dev`. Using development settings for a production build is not a valid build check.
- The backend suite emits one existing structlog exception-formatting warning. It passes; the warning is not concealed.
- Demo seeding idempotency is covered by the suite and was separately verified earlier during runtime setup. This screenshot session preserves existing investigation states.
- CI's dependency-security scan publishes an advisory artifact and currently uses `|| true`. A green CI result therefore does not establish a vulnerability-free dependency set.
- Local service readiness does not establish production resilience or end-to-end tracing coverage.

See [the workflow](../.github/workflows/ci.yml), [Actions history](https://github.com/Gwerdonatus/Sentinel/actions?query=branch%3Afix%2Freliable-audit-pipeline), [local check commands](../README.md#verification) and [screenshot provenance](screenshots/README.md).
