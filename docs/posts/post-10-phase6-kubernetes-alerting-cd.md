# Building Sentinel: Kubernetes, Alerting & CD Pipeline

*Technical companion to [The Operational Envelope](#). Read that first.*

Phase 6 is the infrastructure that makes Sentinel trustworthy in production. Three components: Kubernetes manifests that express operational commitments as code, Prometheus alerting rules that watch Sentinel's own health, and a CD pipeline that deploys reliably with zero manual steps outside of the production approval gate.

Code: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel) — tagged `v0.6.0`.

---

## Kubernetes: Kustomize Base/Overlay Pattern

We use Kustomize rather than raw Helm charts. Kustomize is simpler for a platform that owns its own manifests — no template syntax to learn, no values files to manage, patches are explicit and readable.

Structure:

```
infra/kubernetes/
├── base/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── services.yaml        # Service, HPA, Ingress, ServiceAccounts
│   └── kustomization.yaml
└── overlays/
    ├── production/          # 5 replicas, tighter resource limits
    └── staging/             # 1 replica each, DEBUG logging
```

The base defines the contract. Overlays patch specific values:

```yaml
# overlays/production/kustomization.yaml
patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 5
    target:
      kind: Deployment
      name: sentinel-api
```

This is the cleanest way to manage environment differences — the base is the single source of truth, overlays are minimal diffs. `kubectl apply -k infra/kubernetes/overlays/production` is the entire production deployment command.

---

## Zero-Downtime: The maxUnavailable: 0 Contract

The API deployment rolling update strategy:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1          # One extra pod during the update
    maxUnavailable: 0    # Never fewer than the desired replica count
```

`maxUnavailable: 0` means Kubernetes will never terminate an old pod until a new pod is healthy. The readiness probe must pass before the new pod receives traffic:

```yaml
readinessProbe:
  httpGet:
    path: /health/ready/
    port: http
  initialDelaySeconds: 15
  periodSeconds: 5
  failureThreshold: 2   # Two consecutive failures pulls the pod from rotation
```

`/health/ready/` checks PostgreSQL and Redis. A pod that has started but can't reach its dependencies never enters the load balancer rotation — it fails the readiness probe and Kubernetes keeps routing traffic to the existing healthy pods.

The startup probe handles slow initial startup separately from the liveness probe:

```yaml
startupProbe:
  httpGet:
    path: /health/live/
    port: http
  failureThreshold: 30   # 30 × 10s = 5 minutes max startup time
  periodSeconds: 10
```

This prevents the liveness probe from killing a pod that's legitimately still starting (running migrations, warming caches) by giving it up to 5 minutes before the liveness probe takes over.

---

## The Kafka Consumer Deployment Decision

Every other deployment uses `RollingUpdate`. The Kafka consumer uses `Recreate`:

```yaml
# deployment-worker.yaml (kafka-consumer section)
strategy:
  type: Recreate    # Not RollingUpdate
```

The reason: Kafka partitions can only be assigned to one consumer in a group at a time. During a rolling update with two consumer instances running simultaneously, Kafka triggers a partition rebalance. While rebalancing, no consumer is processing messages from the affected partitions — there's a pause. Depending on timing, the same message could be picked up by both the old and new instance before the rebalance completes.

`Recreate` terminates the old pod completely before starting the new one. There's a brief gap where no consumer is running (usually 10–30 seconds). Events accumulate in Kafka during this gap. The new consumer starts, claims all partitions, and processes from the last committed offset. No duplicate processing, no ambiguous partition state.

This is a deliberate latency-for-correctness trade-off, and it's the right one for a consumer that drives risk scoring. A 30-second gap in risk scoring is visible in the Kafka lag metric. A double-processed event producing two different risk scores for the same event ID is subtle and hard to detect.

The `terminationGracePeriodSeconds: 60` gives the consumer enough time to finish processing the current message and commit its offset before Kubernetes sends SIGKILL:

```python
# consumer.py — SIGTERM handler
def _handle_shutdown(self, signum, frame):
    self._running = False
    # The while loop exits on next poll() iteration
    # consumer.close() is called in the finally block
```

SIGTERM → `_running = False` → current message finishes → offset committed → `consumer.close()` → pod terminates cleanly.

---

## Security Context: Minimal Privilege

Every pod runs with the minimum privilege required:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  runAsGroup: 1001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
```

`readOnlyRootFilesystem: true` is the most operationally significant one. It means an attacker who achieves code execution in the container cannot write to the filesystem — no dropping binaries, no modifying config files. The only writable paths are explicitly mounted `emptyDir` volumes:

```yaml
volumeMounts:
  - name: tmp
    mountPath: /tmp
  - name: staticfiles
    mountPath: /app/staticfiles
volumes:
  - name: tmp
    emptyDir: {}
```

ServiceAccounts have `automountServiceAccountToken: false` — the pod doesn't get a Kubernetes API token it doesn't need, which removes an entire attack vector if the container is compromised.

---

## Prometheus Alerting: Two Alert Paths

This was the key architectural distinction from Phase 3. Sentinel has two independent alert systems serving different purposes:

**Application alerts** (Phase 3 `AlertRule` model):
- Watches audit event data for security anomalies
- Fires when `risk_score > 75` or an AI agent scope-creeps
- Delivered via Slack/email/webhook to security teams
- Stored in PostgreSQL — queryable in investigations

**Infrastructure alerts** (Prometheus rules):
- Watches Sentinel itself for operational health
- Fires when SLA thresholds are breached or components fail
- Routed via Alertmanager to PagerDuty/on-call rotation
- Independent of PostgreSQL — works even if the DB is down

The SLA thresholds are embedded in the rule expressions themselves, making them documentation:

```yaml
- alert: SentinelAPIHighLatency
  expr: |
    histogram_quantile(0.99,
      rate(django_http_requests_latency_seconds_by_view_method_bucket{
        job="sentinel-backend",
        view=~".*ingest.*"
      }[5m])
    ) > 0.5
  for: 5m
  labels:
    severity: high
    sla: event_ingestion_p99
  annotations:
    summary: "Sentinel event ingestion p99 latency exceeds 500ms"
```

The `sla: event_ingestion_p99` label makes this alert queryable as SLA evidence — Prometheus can report on how many times this alert fired in Q3, which is directly usable in compliance conversations.

The `for: 5m` prevents alert fatigue from transient spikes. A single slow request doesn't page anyone. Sustained elevated latency does.

The Kafka consumer lag rules watch the consumer group directly:

```yaml
- alert: SentinelKafkaConsumerLagHigh
  expr: |
    kafka_consumergroup_lag{
      consumergroup=~"sentinel-risk-engine-.*"
    } > 1000
  for: 5m
  labels:
    severity: high
    component: kafka-consumer
```

This fires if the risk engine is more than 1000 events behind real time for 5 consecutive minutes. The runbook linked in the annotations tells the on-call engineer exactly what to check and in what order.

---

## CD Pipeline: Image Digest Pinning

The CD pipeline's most important detail is not the deployment step — it's how images are referenced.

In the base manifests:
```yaml
image: ghcr.io/gwerdonatus/sentinel-backend:latest
```

In every deployment, the pipeline replaces this with the content-addressed digest:

```bash
# In the CD pipeline
BACKEND_DIGEST="${{ needs.build.outputs.digest }}"
sed -i "s|sentinel-backend:latest|sentinel-backend@${BACKEND_DIGEST}|g" \
  infra/kubernetes/overlays/production/kustomization.yaml
```

The result in production:
```yaml
image: ghcr.io/gwerdonatus/sentinel-backend@sha256:a3b8c2d...
```

This is the difference between "we deployed the latest build" and "we deployed commit `abc123` and can prove it." The digest is immutable — `sha256:a3b8c2d...` will always refer to exactly the same image layers. If you need to investigate what code was running during an incident, `git log` plus the image digest gives you a complete, verifiable answer.

The pipeline flow:

```
push to main
    │
    ▼
build job — multi-arch (amd64 + arm64), push to GHCR
    │ outputs: backend-digest, frontend-digest
    ▼
deploy-staging — apply kustomize overlay with pinned digest
    │
    ▼
smoke tests — health/live/, GET /api/v1/ returns 200
    │
    ▼
deploy-production — requires manual approval (GitHub environment protection)
    │
    ▼
post-deploy health check + git tag
```

The `environment: production` block in the workflow requires a reviewer approval before the deploy step runs. This is the manual gate — not an extra check, not a separate approval system, just GitHub's built-in environment protection rules.

---

## Runbooks: Writing for 2am

Three runbooks in `docs/runbooks/`:

**`incident-investigation.md`** — starts from a fired alert and walks through the investigation steps in order: alert detail → actor timeline → API query → integrity verification → compliance export → escalation matrix. Every command is complete and copy-pasteable.

**`kafka-consumer-lag.md`** — diagnosis commands, scaling procedure, bottleneck identification (is it the consumer or the risk engine query performance?), backfill instructions (the answer is: do nothing, Kafka picks up where it left off). Includes the prevention section: set partition count before you need to scale.

**`deployment-rollback.md`** — normal deployment verification checklist, `kubectl rollout undo`, revision history rollback, and the emergency migration reversal procedure with a prominent warning that it should be tested in staging first.

The test for a good runbook: can a new engineer who has never seen Sentinel execute it successfully without asking for help? If yes, it's done. If not, add more detail.

---

## Current Platform Summary

| Phase | What it delivers | Status |
|---|---|---|
| 1 | Foundation: monorepo, Docker, CI, OTel, health endpoints | ✅ |
| 2 | JWT auth, RBAC, immutable audit ledger, HMAC signing | ✅ |
| 3 | AI actor identity, risk engine, alert rules, API keys, notifications | ✅ |
| 4 | Dashboard, BFF auth, actor timeline, compliance reports | ✅ |
| 5 | Kafka, multi-tenancy, Python SDK | ✅ |
| 6 | Kubernetes, Prometheus alerting, CD pipeline, runbooks | ✅ |

**17 ADRs. 567 files. 8 blog posts. 10 Prometheus alerting rules. 12 Kubernetes manifests. 3 runbooks. 6 git tags.**

The platform is complete. Every architectural decision is documented. Every operational procedure is written down.

---

*Star the repo: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*

*v0.6.0 tagged — all phases complete.*
