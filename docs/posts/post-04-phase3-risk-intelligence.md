# Building Sentinel: Risk Intelligence & AI Actor Tracking

*This is the technical companion to [How Do You Audit What an AI Agent Does?](#). Read that first for the problem context — this post covers how we built the answer.*

Phase 3 adds three things to Sentinel: an identity model that gives AI agents real attribution, a risk scoring engine that builds behavioral baselines per actor, and an alert system that turns elevated risk into action within seconds.

Full code: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel) — tagged `v0.3.0`.

---

## Step One: Give AI Agents a Real Identity

Before you can detect anomalous AI behavior, you need to know *which* AI did *what*. This sounds obvious but most systems get it wrong — AI agents typically run under a shared service account, which means every investigation starts by trying to figure out which agent actually made a given call.

We added `actor_type` directly to the `AuditEvent` table:

```python
class ActorType(models.TextChoices):
    HUMAN = "HUMAN", "Human User"
    SERVICE = "SERVICE", "Backend Service"
    AI_AGENT = "AI_AGENT", "AI Agent"
```

This was a non-breaking, additive migration on top of the Phase 2 schema — `actor_type`, `agent_name`, and `risk_score` added with sensible defaults, existing rows backfilled as `HUMAN`:

```python
migrations.AddField(
    model_name="auditevent",
    name="actor_type",
    field=models.CharField(max_length=20, default="HUMAN", db_index=True, ...),
),
migrations.AddField(
    model_name="auditevent",
    name="agent_name",
    field=models.CharField(max_length=128, blank=True, default="", db_index=True, ...),
),
```

**The deliberate choice here was denormalization over a join.** We considered a separate `Actor` table linked by foreign key. We rejected it. Investigation queries during an incident need to be fast — "show me every AI agent event in the last hour" should be a single indexed column scan, not a join through an actor identity table. This follows the same pattern Phase 2 established with `actor_email` and `actor_role`: the audit event is a *snapshot* of who acted, not a live reference to a mutable record. (Full reasoning in [ADR-012](#).)

### API Keys as AI Agent Identity

The mechanism by which an AI agent *proves* it is who it claims to be is an API key — but not a generic one. We built a dedicated identity model:

```python
class APIKey(SoftDeletableModel):
    actor_type = models.CharField(choices=ActorType.choices, ...)
    agent_name = models.CharField(max_length=128, blank=True, default="")
    agent_version = models.CharField(max_length=64, blank=True, default="")
    agent_description = models.TextField(blank=True, default="")
    scopes = models.JSONField(default=list)
```

When you create a key for an AI agent, `agent_name` is required — you cannot issue an anonymous AI credential in Sentinel by design:

```python
def validate(self, attrs: dict) -> dict:
    if attrs.get("actor_type") == ActorType.AI_AGENT and not attrs.get("agent_name"):
        raise serializers.ValidationError(
            {"agent_name": "agent_name is required for AI_AGENT keys."}
        )
    return attrs
```

Key storage follows the same pattern as password hashing — the full key is shown exactly once at creation and never persisted:

```python
@classmethod
def generate_key(cls, environment: str = "live") -> tuple[str, str, str]:
    raw = secrets.token_urlsafe(32)
    full_key = f"sk_{environment}_{raw}"
    key_prefix = full_key[:12]
    key_hash = hmac.new(
        key=settings.SECRET_KEY.encode(),
        msg=full_key.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return full_key, key_prefix, key_hash
```

`key_prefix` enables O(1) lookup without scanning the table; `key_hash` is what's compared on verification, using `hmac.compare_digest` for constant-time comparison. A database breach exposes zero usable credentials.

We wrote a custom DRF authentication backend so AI agents and services authenticate via `Authorization: Bearer sk_live_...` alongside human JWT tokens, in the same request pipeline:

```python
class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[object, APIKey] | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        presented_key = auth_header[7:].strip()
        if presented_key.startswith("eyJ"):  # JWT, not an API key — skip
            return None

        api_key = APIKey.verify_key(presented_key)
        if api_key is None:
            raise AuthenticationFailed("Invalid or expired API key.")

        api_key.record_usage(ip_address=request.META.get("REMOTE_ADDR", ""))
        return api_key.created_by, api_key
```

Every authenticated request now carries enough context — human or AI — to populate `actor_type` and `agent_name` correctly on the resulting audit event.

---

## Step Two: Build Baselines, Not Static Thresholds

This is the part that doesn't transfer from traditional anomaly detection. A static threshold ("alert if more than 1000 requests/hour") is wrong for AI agents because the right number is different for every agent and changes over time as the agent's role evolves.

Every risk signal compares current behavior to that *specific actor's own historical baseline*, not a global constant:

```python
def score_ai_data_volume(
    event: "AuditEvent",
    window_minutes: int = 60,
    volume_threshold_multiplier: float = 10.0,
    baseline_days: int = 7,
) -> SignalResult:
    if event.actor_type != "AI_AGENT" or not event.agent_name:
        return SignalResult("ai_data_volume", 0, False)

    now = timezone.now()
    window_start = now - timedelta(minutes=window_minutes)
    baseline_start = now - timedelta(days=baseline_days)

    current_count = AuditEvent.objects.filter(
        agent_name=event.agent_name,
        actor_type="AI_AGENT",
        event_type__in=DATA_ACCESS_TYPES,
        created_at__gte=window_start,
    ).count()

    baseline_total = AuditEvent.objects.filter(
        agent_name=event.agent_name,
        actor_type="AI_AGENT",
        event_type__in=DATA_ACCESS_TYPES,
        created_at__gte=baseline_start,
        created_at__lt=window_start,
    ).count()

    hourly_baseline = baseline_total / max((baseline_days * 24) - (window_minutes / 60), 1)
    if hourly_baseline < 1:
        return SignalResult("ai_data_volume", 0, False)  # Not enough history yet

    ratio = current_count / hourly_baseline
    if ratio >= volume_threshold_multiplier:
        score = min(95, int(80 + math.log2(ratio / volume_threshold_multiplier) * 5))
        return SignalResult("ai_data_volume", score, True, reason=...)
```

A 10x spike over baseline scores 80. A 20x spike scores 85. The log scale means the score climbs but doesn't explode — a 100x outlier and a 1000x outlier are both "very bad" without one drowning out the meaning of the other.

The companion signal — equally important — looks for *what kind* of access, not just how much:

```python
def score_ai_new_resource_type(event: "AuditEvent", lookback_days: int = 30) -> SignalResult:
    if event.actor_type != "AI_AGENT" or not event.agent_name:
        return SignalResult("ai_new_resource_type", 0, False)

    known_types = set(
        AuditEvent.objects.filter(
            agent_name=event.agent_name,
            actor_type="AI_AGENT",
            created_at__gte=timezone.now() - timedelta(days=lookback_days),
        )
        .exclude(resource_type="")
        .values_list("resource_type", flat=True)
        .distinct()
    )

    if known_types and event.resource_type not in known_types:
        return SignalResult("ai_new_resource_type", 60, True, reason=(
            f"AI agent '{event.agent_name}' accessed new resource type "
            f"'{event.resource_type}'. Known types: {known_types}"
        ))
```

This is the scope-creep detector from the previous post's scenario. A support bot that has only ever touched `user` resources suddenly touching `transaction_history` fires this signal regardless of volume — a single anomalous request is enough.

Human signals exist too, using the same principle. Velocity spike compares an actor's current request rate to their own 7-day baseline:

```python
ratio = current_count / hourly_baseline
if ratio >= spike_multiplier:  # default 5x
    score = min(95, int(70 + math.log2(ratio / spike_multiplier) * 10))
```

Same algorithm shape, same actor-relative comparison, applied to a human's login/action pattern instead of an AI agent's data access pattern.

---

## Step Three: Composite Scoring

A single fired signal shouldn't be the whole story, but it also shouldn't be diluted by averaging against signals that didn't fire. The composite scorer takes the dominant signal and adds a capped contribution from anything else that also fired:

```python
fired = [r for r in results if r.fired]
primary = max(fired, key=lambda r: r.score)
composite = primary.score

secondary_fired = [r for r in fired if r is not primary]
secondary_boost = min(15, len(secondary_fired) * 5)
composite = min(100, composite + secondary_boost)
```

One critical signal at 85 with two moderate secondary signals becomes 85 + 10 = 95. One moderate signal alone stays at its own score — it doesn't get amplified into something it isn't. The dominant signal drives the verdict; secondary signals corroborate it.

Risk levels map directly to score ranges: 0–24 low, 25–49 medium, 50–74 high, 75–100 critical. The engine never raises — any unexpected error returns a score of 0 rather than crashing the pipeline that's processing live events:

```python
def score(self, event: "AuditEvent") -> RiskScore:
    try:
        return self._score(event)
    except Exception as exc:
        logger.error("risk_engine_error", event_id=str(event.id), error=str(exc), exc_info=True)
        return RiskScore(score=0, level=RiskLevel.LOW, explanation="Risk scoring failed.")
```

Fail open, not closed. A bug in the risk engine should never become an outage in the audit pipeline.

---

## Step Four: Alert Rules — Why We Rejected eval()

Every alert rule needs a condition. The tempting shortcut is a string DSL — `risk_score > 80 AND actor_type = 'AI_AGENT'` — parsed and evaluated, or worse, passed straight to Python's `eval()`.

We rejected both. `eval()` on any string that could ever originate from user input, even indirectly, is a remote code execution vector. That's disqualifying for a security product regardless of how convenient it would be.

A custom DSL avoids `eval()` but requires writing and maintaining a parser — tokenizing, operator precedence, quoting, escaping. All solvable, none of it worth solving when JSON already does the job:

```python
{
    "operator": "AND",
    "conditions": [
        {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
        {"field": "risk_score", "operator": "gte", "value": 50}
    ]
}
```

The evaluator is a recursive function over this structure, with nine operators (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, `is_null`) and support for `AND`/`OR` composition:

```python
def evaluate_condition(condition: dict, event: "AuditEvent", risk_level: str = "") -> bool:
    operator = condition.get("operator", "").lower()

    if operator == "and":
        return all(evaluate_condition(c, event, risk_level) for c in condition["conditions"])
    if operator == "or":
        return any(evaluate_condition(c, event, risk_level) for c in condition["conditions"])

    field = condition["field"]
    actual = _get_field_value(event, field, risk_level)
    return _apply_operator(operator, actual, condition["value"], field)
```

Conditions live in a `JSONField` on `AlertRule` — directly storable, directly queryable, inspectable in Django admin without a custom renderer, and trivially serializable through the API. No injection surface, no parser to maintain. Full reasoning in [ADR-013](#).

Five built-in rules ship pre-seeded via migration, including the two that map directly to the AI threat model from the previous post:

```python
{
    "name": "High Risk AI Agent Action",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
            {"field": "risk_score", "operator": "gte", "value": 50},
        ],
    },
    "notification_channels": ["slack"],
},
{
    "name": "AI Agent Accessing New Resource Type",
    "condition": {
        "operator": "AND",
        "conditions": [
            {"field": "actor_type", "operator": "eq", "value": "AI_AGENT"},
            {"field": "risk_score", "operator": "gte", "value": 55},
        ],
    },
    "notification_channels": ["slack", "email"],
},
```

---

## The One Deliberate Exception to Immutability

Phase 2 established that audit events are append-only — the repository raises `NotImplementedError` on update, full stop. Phase 3 needed to write a computed `risk_score` onto every event, *after* creation, because scoring requires historical context that doesn't exist yet at the moment the event itself is recorded.

This is a real tension, and we didn't paper over it. The risk service bypasses the repository's immutability guard — deliberately, narrowly, and only for this one field:

```python
# We use update() directly to bypass the immutability guard on the service
# layer — risk_score is a system-computed field added after creation,
# not a user-modifiable field. This is documented as the sole exception.
AuditEvent.objects.filter(id=event.id).update(risk_score=risk_score.score)
```

Two things make this acceptable rather than a quiet erosion of the Phase 2 guarantee:

**The HMAC signature doesn't cover `risk_score`.** The signature from Phase 2 is computed over `event_type`, `actor_id`, `actor_email`, `created_at`, and the metadata hash — the facts of *what happened*. It was never extended to include `risk_score`, precisely because that field needed to remain writable. The cryptographic proof of the original event content is completely untouched by this exception.

**The exception is narrow and explicit, not a backdoor.** Only `RiskService.process_event` writes this field. Only via direct `update()`, never `save()`. Every other code path — views, the audit ingestion API, the `@audit_action` decorator — still hits the repository, which still raises. One call site, one field, fully documented in [ADR-014](#) for anyone auditing the security model itself.

This is the kind of judgment call that's worse to leave implicit. A system that quietly bent its own immutability rule would be a liability. A system that names the exception, scopes it precisely, and explains why the signature doesn't cover it — that's defensible under scrutiny, including the scrutiny of an actual compliance audit.

---

## Closing the Loop: Notifications

A fired alert that nobody sees isn't a security feature. Each notification channel is an independent Celery task so a failed Slack webhook doesn't block email delivery:

```python
for channel in channels:
    if channel == "slack":
        deliver_slack_task.delay(alert_id, config.get("slack", {}))
    elif channel == "email":
        deliver_email_task.delay(alert_id, config.get("email", {}))
    elif channel == "webhook":
        deliver_webhook_task.delay(alert_id, config.get("webhook", {}))
```

Outbound webhooks carry an HMAC-SHA256 signature header so the receiving system can verify the alert genuinely came from Sentinel:

```python
signature = hmac.new(key=secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
headers = {"X-Sentinel-Signature": f"sha256={signature}", "X-Sentinel-Alert-ID": str(alert.id)}
```

Every delivery attempt — success or failure — is recorded directly on the `Alert` record, so the delivery history is itself part of the audit trail.

---

## Current API Surface

```
POST   /api/v1/api-keys/create/              Create key (human, service, or AI agent)
GET    /api/v1/api-keys/                     List keys
DELETE /api/v1/api-keys/{id}/                Revoke key

GET    /api/v1/alerts/                       List alerts (filtered: severity, actor_type, agent_name)
GET    /api/v1/alerts/{id}/                  Alert detail
POST   /api/v1/alerts/{id}/acknowledge/      Acknowledge
POST   /api/v1/alerts/{id}/resolve/          Resolve with note
GET    /api/v1/alerts/rules/                 List rules
POST   /api/v1/alerts/rules/                 Create rule
DELETE /api/v1/alerts/rules/{id}/            Deactivate rule

GET    /api/v1/risk/summary/                 Platform-wide risk summary
GET    /api/v1/risk/actors/{actor_id}/       Actor risk profile (human or AI)
```

`GET /api/v1/risk/summary/` is the one built specifically with the AI angle in mind — it surfaces `top_risky_ai_agents` directly, so the answer to "which of our AI agents should I be worried about right now" is one API call, not a manual log dig.

---

## What's Next

Phase 4 builds the dashboard: an actor timeline view that reconstructs any human or AI session end-to-end, an alert management inbox, and compliance report export with AI action attribution built in — so a SOC 2 or PCI-DSS evidence package can show not just "data was accessed" but "by this named AI agent, version X, within its expected scope."

The risk engine built in this phase is the data source. Every score, every fired signal, every alert becomes a row in the investigation view.

---

*Star the repo: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*

*v0.3.0 tagged. Phase 4 in progress.*
