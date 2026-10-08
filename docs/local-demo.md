# Local Demo Walkthrough

The demo dataset is synthetic and exists only for local development and portfolio
screen recordings. Generated events contain `metadata.demo_data=true`.

## Start

```bash
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

The first run prints a test API key once. Never record or publish that key.
Subsequent runs preserve the key, agent identity, and nine synthetic events.
Run the command twice to verify this. Risk scores and alerts appear asynchronously
after Celery publishes the outbox and the Kafka consumer processes the events.

Open `http://localhost:3000` and sign in with:

- Email: `demo.admin@sentinel.local`
- Password: `SentinelDemo123!`

## Demonstration path

1. Open **AI Agents** and select `reconciliation-agent`.
2. Show its normal `support_ticket` history.
3. Open the synthetic `transfer` event and its risk score.
4. Open **Alerts** and show the rule linked to that event.
5. Open **API Keys** to show the agent identity and limited `events:write` scope.

## Failure recovery

Stop Kafka, create an event, and inspect the pending outbox row:

```bash
docker compose stop kafka
docker compose exec backend python manage.py shell
```

The audit event remains in PostgreSQL and its outbox entry remains unpublished.
After Kafka restarts, the periodic publisher retries it and the consumer scores the
event. This demonstrates recovery of publication intent, not synchronous scoring.

## Honest security boundary

Sentinel derives actor identity from the JWT or API key. The submitting system still
reports the business action and resource metadata. Sentinel provides authenticated,
tamper-evident reporting and behavioural monitoring; it is not independent proof
that an uninstrumented action never occurred.

## Local runtime checks

Compose uses service-specific checks: Django and Next.js HTTP endpoints, a targeted
Celery worker ping, Beat's live PID and Redis connectivity, Flower's authenticated
HTTP endpoint, and the Kafka consumer process plus broker metadata. Wait for
initialization before diagnosing a service marked `starting`.

The worker consumes `default`, `high_priority`, and the legacy `celery` queue so
previously queued work is retained. New tasks use `default`. Beat stores its PID
and schedule under `/tmp`, rather than writing runtime files into the checkout.

PostgreSQL and Redis are reachable on the Compose network without publishing
host ports. PostgreSQL preloads `pg_stat_statements`. Nginx routes
`/api/internal/` to Next.js so cookie-based login also works through
`http://localhost`; Django's versioned API remains under `/api/v1/`.

OpenTelemetry 0.49 removes the legacy `pkg_resources` import and fixes context
cleanup for tasks published without trace headers (for example, Beat tasks).
The SDK/exporter versions are kept compatible with the instrumentation version.
CI checks instrumented WSGI startup as well as migration consistency and Compose
configuration.

Slack/email delivery requires explicit notification destinations. The local
walkthrough verifies persisted in-app alerts; it does not send external messages.
Production notification delivery and Kafka consumer-lag monitoring require the
additional integrations documented in the infrastructure configuration.

Next.js development output lives in a separate `.next-dev` volume so production
checks do not corrupt hot-reload assets. PostCSS compiles Tailwind utilities for
both development and production. Run frontend production checks in an isolated
container with `docker compose run --rm --no-deps -e NODE_ENV=production
-e NEXT_DIST_DIR=.next frontend npm run build`.

The audit log, event detail, and alert detail pages support the walkthrough:
open an alert, inspect its explanation, follow the triggering event, and return
to the actor timeline. Nginx resolves Docker service names dynamically so a
container recreation does not leave stale upstream addresses.

## Isolated backend regression checks

Run the suite in test mode so Celery uses its in-memory broker and regression events never reach the running demo worker or Kafka topic. Development dependencies are installed only in the disposable container:

```sh
docker compose run --rm --no-deps --user root \
  -e ENVIRONMENT=test -e KAFKA_ENABLED=False -e OTEL_ENABLED=False \
  backend sh -c 'pip install -r requirements-dev.txt && pytest --cov=sentinel --cov-report=term-missing'
```

The Sentinel 2 homepage is at `/`, the integration guide at `/developers`, and the scoped frontend/backend status view at `/status`. See [the interface conventions](design-system.md).

## Recording rehearsal (about three minutes)

1. **Homepage, 20 seconds.** “Sentinel 2 makes activity across people, services and AI agents visible in one workspace.” Show the logo and enter the workspace.
2. **Overview, 30 seconds.** “Color follows actual severity: critical is red, high is amber, medium is yellow, and low is green. The banner reflects the highest open severity.” Show the priority inbox and current counts. Counts reflect investigation state; acknowledging an alert changes the open count.
3. **AI agent timeline, 40 seconds.** Select `reconciliation-agent`, show its normal support-ticket history, then open its synthetic transfer event. “This change in behavior receives a risk score of 60. It is a monitoring signal, not proof of prompt injection.”
4. **Alert investigation, 40 seconds.** Open the linked alert and show the explanation and triggering event. Explain acknowledge/resolve controls without changing the recording dataset during rehearsal.
5. **Identity and integration, 30 seconds.** Show the demo API key's agent identity and limited scope; keep actual key material off screen. Open the developer guide to show ingestion and the real schema.
6. **Close, 20 seconds.** “The audit outbox preserves publication intent; Kafka triggers scoring; alerts are idempotent. This walkthrough uses clearly labeled synthetic data.”

Rehearsal does not need a new account, new credentials or external notifications. Preserve existing acknowledged/resolved alerts; seeding does not reset investigation history. The optional Kafka failure-recovery sequence above is a separate technical segment.
