# Runbook: Kafka Consumer Lag

**Audience:** Platform engineers  
**Alert:** SentinelKafkaConsumerLagHigh (lag > 1000), SentinelKafkaConsumerDown  
**Impact:** Risk scores falling behind real time. Alerts may be delayed.

---

## Understanding the Lag

Consumer lag = events in Kafka not yet processed by the risk engine.

Lag > 1000 means risk scores are at least 1000 events behind the audit ledger. This is not a data loss situation — events are still being recorded correctly in PostgreSQL. The risk engine is just slower than ingestion.

Acceptable lag: < 100 events (near real-time)  
Warning threshold: 1000 events  
Critical threshold: 10,000 events (risk scoring multiple minutes behind)

---

## Diagnosis

```bash
# Check consumer group lag via Kafka CLI (in the kafka pod)
kubectl exec -n sentinel kafka-0 -- \
  kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group sentinel-risk-engine-production \
  --describe

# Check consumer pod status
kubectl get pods -n sentinel -l app.kubernetes.io/component=kafka-consumer

# Check consumer logs for errors
kubectl logs -n sentinel deployment/sentinel-kafka-consumer --tail=100 | grep -E "ERROR|WARN"

# Check if risk scoring itself is slow (check Celery task timing in Flower)
# http://localhost:5555 or kubectl port-forward
```

---

## Immediate Mitigation

### Scale the consumer

```bash
# Increase replicas to match Kafka partition count
# Each replica handles a subset of partitions
kubectl scale deployment/sentinel-kafka-consumer \
  -n sentinel \
  --replicas=3

# Verify scaling
kubectl rollout status deployment/sentinel-kafka-consumer -n sentinel
```

**Note:** Scaling beyond the partition count has no effect. Check the current partition count:

```bash
kubectl exec -n sentinel kafka-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic sentinel.default.audit.events \
  | grep Partitions
```

### Identify the bottleneck

```bash
# Check if the risk engine is slow (database queries)
kubectl exec -n sentinel deployment/sentinel-kafka-consumer -- \
  python manage.py shell -c "
from django.db import connection
from sentinel.audit.models import AuditEvent
import time
start = time.time()
AuditEvent.objects.filter(actor_id='00000000-0000-0000-0000-000000000000').count()
print(f'Query time: {time.time() - start:.3f}s')
"
```

If query time > 100ms, the issue is database query performance, not consumer throughput. Check PostgreSQL slow query log and ensure indexes on `actor_id, created_at` are present.

---

## If Consumer Is Down (SentinelKafkaConsumerDown)

```bash
# Check pod events for crash reason
kubectl describe pod -n sentinel \
  -l app.kubernetes.io/component=kafka-consumer

# Restart the consumer
kubectl rollout restart deployment/sentinel-kafka-consumer -n sentinel

# Watch logs on restart
kubectl logs -n sentinel -l app.kubernetes.io/component=kafka-consumer \
  --follow --since=30s
```

Common causes:
- Kafka broker unreachable (check `kubectl get pods -n sentinel kafka-0`)
- OOM killed (increase memory limits)
- Kafka rebalance stuck (restart consumer, wait for rebalance to complete)

---

## Backfill After Extended Downtime

If the consumer was down for > 30 minutes and lag has accumulated significantly:

```bash
# The consumer resumes from last committed offset automatically on restart.
# No manual backfill needed — this is the key benefit of Kafka over Redis/Celery.

# Monitor lag decreasing after restart
watch -n 5 "kubectl exec -n sentinel kafka-0 -- \
  kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group sentinel-risk-engine-production \
  --describe | grep sentinel.default.audit.events"
```

---

## Prevention

- Set partition count to 3x the expected consumer replica count
- Monitor p99 risk scoring latency (SentinelRiskScoringHighLatency alert)
- Keep kafka-consumer HPA configured even if not actively scaling
