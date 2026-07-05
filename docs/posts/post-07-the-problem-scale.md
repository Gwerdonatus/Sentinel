# The Infrastructure Question Nobody Asks Until It's Urgent

*This is the seventh post in the Sentinel series. Previous: [Building Sentinel: Dashboard & Compliance Reports](#).*

There's a predictable arc to how security infrastructure gets built at fintech companies.

Phase one: something goes wrong. A disputed transaction, a compromised account, a regulator asking for evidence. The company realizes it doesn't have the visibility it needs, and someone builds the minimum viable audit system — usually a logging table and a dashboard that queries it directly.

Phase two: the company grows. More customers, more engineers, more AI agents with production access. The audit table has 50 million rows. Every dashboard query takes 8 seconds. The logging table is now the slowest thing in the system.

Phase three: the company gets a second customer. A B2B opportunity, a white-label deal, a new subsidiary. The audit system was built for one organization. Now two organizations' data is in the same table with nothing separating them except a `client_id` column someone added manually and forgot to index.

Phase four: the company realizes it needs real-time detection, not batch processing. But the audit pipeline is synchronous — events are written to the database and scored in the same request. Under load, the p99 latency on the audit ingest endpoint is 2 seconds. Every financial action now adds 2 seconds to the user-facing response.

These aren't hypothetical failure modes. They happen in sequence, predictably, to almost every team that builds audit infrastructure by starting with what's immediately needed and deferring scalability decisions.

Phase 5 of Sentinel is about addressing all four before they become emergencies.

---

## The Multi-Tenancy Problem Is Worse Than It Looks

The intuitive solution to "we need multiple organizations in the same system" is to give each one its own database schema. One schema per tenant, completely isolated, clean separation at the database level.

This works until it doesn't. The breaking point is connection pooling.

PostgreSQL has a default connection limit of 100 (configurable, but with real memory costs per connection). When your application connects to a database, it's connecting to a specific database server — not to a specific schema. A connection pool that can handle 10 concurrent connections per schema means 100 tenants consume your entire PostgreSQL connection budget. At 200 tenants, you're either connection-starved or running a connection pooler with its own operational complexity.

The migration problem is worse. Schema-per-tenant means every Django migration has to run against every schema separately. A deployment that takes 30 seconds for one schema takes 50 minutes for 100 schemas. Teams that encounter this usually build custom migration runners, which are a source of their own bugs.

The correct approach — row-level isolation with a `tenant_id` column — doesn't have these problems. One connection pool serves all tenants. Migrations run once. Cross-tenant platform-level queries are a filter away. The tradeoff is that isolation is enforced in application code rather than database structure, which requires discipline in the query layer.

The discipline is enforced by a custom queryset manager. Every scoped model's default queryset exposes `for_tenant()`. Every view calls it. The pattern is impossible to forget accidentally — it's the only way to write a query that returns data.

---

## Why Kafka Is Not Optional at Scale

Phase 1 through 4 ran risk scoring synchronously. An audit event arrives, gets written to PostgreSQL, the Celery task fires, the risk engine queries 30 days of historical data, computes a score, writes it back, evaluates alert rules — all in a chain that has to complete before the next event can be processed.

This works at low volume. It breaks at fintech scale.

The problem isn't the individual latency of any one step — the risk engine query might take 200ms, which is fine in isolation. The problem is that Celery with Redis as the broker has no backpressure mechanism. When events arrive faster than they can be processed, the Redis queue grows. When the queue grows large enough, Celery workers start competing for the same tasks, consumers can't keep up, and the "real-time" in "real-time risk detection" quietly becomes "5 minutes ago."

More critically: if the Celery worker crashes, events in the queue are gone. Redis doesn't have durable, ordered, replayable storage. "The risk engine was down for 20 minutes" means "we have no risk scores for 20 minutes of events." In a financial system during an active fraud attempt, those are exactly the minutes that matter.

Kafka solves both problems. Events accumulate in ordered, durable topic partitions. If the consumer goes down, it picks up exactly where it left off when it restarts. The consumer commits offsets only after successful processing — no event is ever silently dropped. Multiple consumer instances share the partition load automatically through consumer groups. And because topics are partitioned by actor ID, all events from the same actor are processed in order by the same consumer instance — which is exactly what the velocity spike and baseline detection algorithms need.

---

## The SDK Problem Is a Distribution Problem

Here's the sequence of events that happens when a company wants to integrate with Sentinel:

1. Engineer finds the API documentation.
2. Engineer writes code to format the correct JSON payload.
3. Engineer adds the Authorization header.
4. Engineer adds retry logic for network failures.
5. Engineer decides whether to make the audit call synchronous (adds latency) or async (adds complexity).
6. Engineer deploys, discovers that error responses look different from success responses, fixes the parsing.
7. Three months later, a different engineer on a different service goes through steps 1–6 again.

This is the SDK problem. It's not about functionality — the API is fine. It's about the barrier to adoption. Every integration that requires custom HTTP client code is an integration that might be skipped, done incorrectly, or done once and never maintained.

The SDK condenses steps 1–6 into:

```python
from sentinel_sdk import SentinelClient
client = SentinelClient(api_key="sk_live_...")
client.record("TRANSFER_INITIATED", resource_type="transfer", resource_id=txn_id)
```

Three lines. The retry logic, the authentication, the payload formatting, the error handling — all handled. `fail_silent=True` by default means a Sentinel outage never takes down a financial service that just wants to record an event.

For AI agents specifically, the SDK has a pattern that matters: one client instance per agent, with `actor_type=AI_AGENT` and `agent_name` baked into the client at construction. Every event that client records is automatically attributed to that named agent. The person deploying a new AI agent doesn't have to remember to set actor attribution on every call — it's structural.

---

## What This Changes About the Platform

Phase 5 completes the infrastructure layer. Sentinel can now:

- Serve multiple organizations from the same deployment with strict data isolation
- Process millions of events per day without synchronous bottlenecks
- Recover from consumer failures without losing events
- Be adopted by any Python service in three lines of code

The next phase — Kubernetes deployment, Prometheus alerting rules, SLA monitoring — is about making the platform production-reliable at the operational level. The architectural decisions are done. What remains is the operational envelope around them.

Next post: how we built it — the row-level tenant queryset pattern, the Kafka producer with the `_NoOpProducer` fallback that keeps development frictionless, the consumer's offset commit strategy, and why the SDK's `fail_silent` default is a deliberate product decision, not just defensive coding.

---

*Sentinel is open source: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*
