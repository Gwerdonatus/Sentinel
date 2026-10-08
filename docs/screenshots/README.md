# Product screenshots

Captured from the running local Sentinel 2 application on 9 October 2026, at a 1440 × 1000 browser viewport. These are browser screenshots, not generated mockups or reconstructed screens.

## Scenario and boundaries

The fictional Stripe scenario is synthetic test data. Stripe is a reference for a payments-company use case, not a customer, partner or live integration. No payment was executed and no external account permission was changed.

A synthetic support bot has eight routine `support_ticket` events before reporting a `TRANSFER_INITIATED` event against a new `transfer` resource. The new-resource rule produces a score of 60 and two alerts. A synthetic human reports `USER_ROLE_CHANGED` after a network change and outside the configured UTC office hours. The two signals produce a score of 90 and three alerts. These are recorded activity reports, not independently observed bank transactions or proven attacks.

The scenario events were created through Sentinel's audit service, persisted with their outbox entries, published to Kafka and scored by the consumer. This scenario did not exercise HTTP ingestion or increment API-key usage counters. The key listing therefore correctly shows zero uses. No complete API key appears in these images.

The repository's `seed_demo` command provides a smaller repeatable demonstration using `reconciliation-agent`; it does not recreate the additional human scenario or reset acknowledged/resolved alerts. See [local-demo.md](../local-demo.md).

## Images

| Image | What it demonstrates |
|---|---|
| [Overview](overview.jpg) | Five open alerts, severity hierarchy and investigation entry points |
| [AI alert](ai-alert.jpg) | Score 60 with the new-resource explanation |
| [Human alert](human-alert.jpg) | Score 90 with network-change and off-hours signals |
| [AI agents](ai-agents.jpg) | Registered agent identities and recent activity |
| [Alert inbox](alerts.jpg) | Severity, investigation state and linked incidents |
| [Actor timeline](agent-timeline.jpg) | Routine baseline followed by an elevated event |
| [Audit log](audit-log.jpg) | Human and AI activity, resource attribution and computed scores |
| [API keys](api-keys.jpg) | Agent identity, limited scope and visible prefixes only |
| [Evidence reports](reports.jpg) | Completed PDF generation with event totals and named-agent attribution |
| [Homepage](homepage.jpg) | Product identity and workspace/API entry points |

Counts and timestamps describe a local snapshot. They are not production usage, throughput measurements or security guarantees. Report exports support evidence review; they do not confer compliance certification.
