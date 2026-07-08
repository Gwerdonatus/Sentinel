# Runbook: Incident Investigation

**Audience:** Security analysts and on-call engineers  
**Updated:** Phase 6  
**Related alerts:** SentinelAPIHighErrorRate, SentinelAuditPipelineStalled

---

## Overview

This runbook covers how to investigate a security incident using Sentinel's own audit ledger — including the meta-case where Sentinel itself is behaving unexpectedly.

Every action in Sentinel produces an audit event. Every audit event has a `request_id` that traces through to Django logs and OpenTelemetry spans. An investigation always starts with one of three entry points: a fired alert, a specific actor, or a specific time window.

---

## Step 1: Start from an Alert

When an alert fires, navigate to:

```
Dashboard → Alerts → [alert ID]
```

The alert detail view shows:
- The rule that fired and its condition
- The actor (human or AI agent) who triggered it
- The risk score and which signals fired
- The exact `audit_event_id` that crossed the threshold

Click `audit_event_id` to see the raw event, including `request_id`.

**From the request_id**, you can pull the full distributed trace:

```bash
# In Grafana/Tempo — search by trace context
curl -s "http://localhost:3001/api/datasources/proxy/1/loki/api/v1/query_ranges" \
  -d 'query={job="sentinel-backend"} | json | request_id="<REQUEST_ID>"'
```

---

## Step 2: Investigate an Actor

If you know the actor (human user ID or AI agent name), use the actor timeline:

```
Dashboard → /actors/{actor_id}
```

This shows:
- Risk score history (Recharts timeline)
- Every event in the last 30 days, chronologically
- Open alerts for this actor

For AI agents, look for:
- `ai_new_resource_type` signals — agent accessing resources it never has before
- `ai_data_volume` signals — 10x+ volume spike over baseline
- `agent_name` changing across events — could indicate a key being shared

---

## Step 3: Query the Audit Ledger Directly

For complex investigations, use the audit event API directly:

```bash
# All events from a specific AI agent in the last 2 hours
curl -s "https://api.sentinel.io/api/v1/events/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -G \
  --data-urlencode "agent_name=support-bot-v2" \
  --data-urlencode "from_dt=$(date -u -d '2 hours ago' +%Y-%m-%dT%H:%M:%SZ)" \
  | jq '.results[] | {time: .created_at, type: .event_type, resource: .resource_type, score: .risk_score}'

# All high-risk events in the last hour
curl -s "https://api.sentinel.io/api/v1/events/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -G \
  --data-urlencode "from_dt=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  | jq '.results[] | select(.risk_score >= 50)'
```

---

## Step 4: Verify Audit Record Integrity

If a record's authenticity is in question:

```bash
curl -s "https://api.sentinel.io/api/v1/events/{EVENT_ID}/verify/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq '{valid: .valid, message: .message}'
```

`"valid": true` — record unmodified since creation.  
`"valid": false` — record tampered. Escalate immediately. Preserve the raw database row before any further action.

---

## Step 5: Generate a Compliance Evidence Package

For regulatory or legal requests:

```
Dashboard → Compliance → Request Report → SOC 2 / PCI-DSS / Custom
```

Or via API:

```bash
curl -s -X POST "https://api.sentinel.io/api/v1/compliance/reports/" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "custom",
    "report_format": "pdf",
    "from_dt": "2025-01-01T00:00:00Z",
    "to_dt": "2025-03-31T23:59:59Z",
    "filters": {"actor_type": "AI_AGENT"}
  }'
```

Poll `GET /api/v1/compliance/reports/{id}/` until `status == "ready"`, then download.

---

## Escalation

| Situation | Action |
|---|---|
| Tampered audit record detected | Escalate to CISO immediately. Preserve DB state. Do not modify. |
| AI agent with critical risk score (75+) | Revoke API key immediately via dashboard or `DELETE /api/v1/api-keys/{id}/` |
| Platform-wide alert rule firing continuously | Check Prometheus for infrastructure issues. See SentinelAPIDown runbook. |
| Kafka consumer lag > 5000 | Scale kafka-consumer deployment. See Kafka consumer lag runbook. |

---

## Key Commands Reference

```bash
# Acknowledge an alert
curl -X POST "https://api.sentinel.io/api/v1/alerts/{id}/acknowledge/" \
  -H "Authorization: Bearer $TOKEN"

# Revoke a compromised AI agent key
curl -X DELETE "https://api.sentinel.io/api/v1/api-keys/{key_id}/" \
  -H "Authorization: Bearer $TOKEN"

# Check Kafka consumer lag (in Kubernetes)
kubectl exec -n sentinel deployment/sentinel-kafka-consumer -- \
  python manage.py run_kafka_consumer --help

# Force a full platform health check
curl -s "https://api.sentinel.io/health/" | jq .
```
