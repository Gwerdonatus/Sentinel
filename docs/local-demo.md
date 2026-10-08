# Local Demo Walkthrough

The demo dataset is synthetic and exists only for local development and portfolio
screen recordings. Generated events contain `metadata.demo_data=true`.

## Start

```bash
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

The command prints a rotated test API key once. Never record or publish that key.

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
