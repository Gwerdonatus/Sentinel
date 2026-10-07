# Runbook: Deployment & Rollback

**Audience:** Platform engineers  
**Related pipeline:** .github/workflows/cd.yml

---

## Normal Deployment

Application or infrastructure changes on `main` trigger the CD pipeline automatically:

1. Docker images built and pushed to GHCR with content-addressed digest
2. Deployed to staging when `ENABLE_STAGING_DEPLOY=true` is configured
3. Smoke tests run against staging
4. Production deployment requires manual approval in GitHub Actions

To approve a production deploy:
1. Go to the repository → Actions → CD workflow run
2. Click the pending "Deploy to Production" step
3. Click "Review deployments" → Approve

---

## Verify a Deployment

```bash
# Check rollout status
kubectl rollout status deployment/sentinel-api -n sentinel
kubectl rollout status deployment/sentinel-worker -n sentinel

# Verify the deployed image digest matches what CI built
kubectl get deployment sentinel-api -n sentinel \
  -o jsonpath='{.spec.template.spec.containers[0].image}'

# Health check
curl -s https://api.sentinel.io/health/ | jq '{status: .status, checks: .checks}'

# Confirm API version bumped
curl -s https://api.sentinel.io/api/v1/ | jq .version
```

---

## Rollback

### Immediate rollback (last known good)

```bash
# Roll back the API deployment
kubectl rollout undo deployment/sentinel-api -n sentinel

# Roll back the worker
kubectl rollout undo deployment/sentinel-worker -n sentinel

# Watch the rollback
kubectl rollout status deployment/sentinel-api -n sentinel

# Verify health after rollback
curl -s https://api.sentinel.io/health/ready/ | jq .status
```

### Roll back to a specific revision

```bash
# List revision history
kubectl rollout history deployment/sentinel-api -n sentinel

# Roll back to revision 3
kubectl rollout undo deployment/sentinel-api -n sentinel --to-revision=3
```

### Roll back database migrations (last resort)

Migrations are designed to be additive (Phase 5 policy). If a migration must be reversed:

```bash
# SSH into a migration pod or exec into the API pod
kubectl exec -it -n sentinel deployment/sentinel-api -- bash

# List migration history
python manage.py showmigrations

# Reverse a specific migration (DANGEROUS — test in staging first)
python manage.py migrate sentinel_audit 0001_initial
```

---

## Zero-Downtime Deploy Verification Checklist

After every production deployment:

- [ ] `kubectl rollout status` shows `successfully rolled out` for all deployments
- [ ] `GET /health/ready/` returns `{"status": "ready"}`
- [ ] `GET /api/v1/` returns the new version string
- [ ] Prometheus shows no spike in 5xx error rate
- [ ] Kafka consumer lag is < 100 events (check Grafana)
- [ ] No new open alerts in Sentinel dashboard

---

## Emergency Contacts

| Situation | Contact |
|---|---|
| Database migration failure | Database admin on-call |
| Kafka broker failure | Infrastructure on-call |
| Security incident (tampered audit record) | CISO + Legal immediately |
