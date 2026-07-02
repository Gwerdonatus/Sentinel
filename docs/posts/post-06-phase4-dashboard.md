# Building Sentinel: Dashboard & Compliance Reports

*Technical companion to [The Investigation Problem](#). Read that first.*

Phase 4 converts Sentinel from an API into a product — the dashboard a security team actually uses to investigate incidents. Three things had to be built correctly: authentication that doesn't undermine the platform's own security guarantees, a UI architecture that makes investigation fast enough to be useful, and compliance reports that show AI actor attribution as the headline, not a footnote.

Code: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel) — tagged `v0.4.0`.

---

## Authentication: The Backend-for-Frontend Pattern

The problem with standard SPA JWT storage was laid out in the previous post. The implementation decision: httpOnly cookies set and read exclusively by Next.js Route Handlers — the browser never touches the token, no JavaScript can read it, XSS is not a token exfiltration path.

The architecture has three layers:

```
Browser (no tokens)
    ↓ /api/internal/auth/login (POST email+password)
Next.js Route Handler (sets httpOnly cookies)
    ↓ /api/v1/auth/login/ (Bearer token internally)
Django Backend (issues JWT pair)
```

The login route handler:

```typescript
// /api/internal/auth/login/route.ts

export async function POST(request: NextRequest) {
  const body = await request.json();

  const backendResponse = await fetch(`${BACKEND_URL}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await backendResponse.json();
  if (!backendResponse.ok) {
    return NextResponse.json(data, { status: backendResponse.status });
  }

  // Return ONLY the user object to the client — never the tokens themselves
  const response = NextResponse.json({ user: data.user });

  response.cookies.set("sentinel_access", data.access, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 15 * 60, // matches JWT_ACCESS_TOKEN_LIFETIME_MINUTES
  });
  response.cookies.set("sentinel_refresh", data.refresh, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 60 * 60, // matches JWT_REFRESH_TOKEN_LIFETIME_DAYS
  });

  return response;
}
```

The client context stores only the user object, not any credential:

```typescript
// AuthProvider — no token state anywhere
const [user, setUser] = useState<User | null>(null);

useEffect(() => {
  fetch("/api/internal/auth/session")
    .then(r => r.json())
    .then(data => setUser(data.user ?? null));
}, []);
```

### The Proxy Route with Silent Refresh

Every API call from the dashboard goes through a catch-all proxy route that reads the access token cookie server-side, attaches it as a Bearer header, and forwards the request to Django:

```typescript
// /api/internal/proxy/[...path]/route.ts

async function handler(request: NextRequest, { params }) {
  const { path } = await params;
  const accessToken = request.cookies.get("sentinel_access")?.value;
  const refreshToken = request.cookies.get("sentinel_refresh")?.value;

  if (!accessToken) {
    return NextResponse.json({ error: { code: "no_session" } }, { status: 401 });
  }

  let backendResponse = await forwardRequest(request, path, accessToken);

  // 401 from backend = expired access token — try silent refresh
  if (backendResponse.status === 401 && refreshToken) {
    const newAccessToken = await refreshAccessToken(refreshToken);

    if (newAccessToken) {
      backendResponse = await forwardRequest(request, path, newAccessToken);
      const response = new NextResponse(await backendResponse.text(), {
        status: backendResponse.status,
      });
      // Update the cookie with the new token — transparent to the client
      response.cookies.set("sentinel_access", newAccessToken, { httpOnly: true, ... });
      return response;
    }

    // Refresh token itself expired — clear cookies and signal session end
    const response = NextResponse.json({ error: { code: "session_expired" } }, { status: 401 });
    response.cookies.delete("sentinel_access");
    response.cookies.delete("sentinel_refresh");
    return response;
  }

  return new NextResponse(await backendResponse.text(), { status: backendResponse.status });
}
```

The result: the client component calls `/api/internal/proxy/alerts` and gets back alert data. It never knows that a token refresh happened in the middle. The token rotation the backend enforced in Phase 2 works transparently.

The client-side API client is correspondingly simple:

```typescript
// lib/dashboard-api.ts — all it does is call our own proxy
export const dashboardApi = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>("GET", path, undefined, options),
  post: <T>(path: string, body?: unknown) =>
    request<T>("POST", path, body),
};
```

---

## TanStack Query: No fetch-in-useEffect Anywhere

Eight views, each with multiple data sources. Without a state management layer, this becomes eight versions of the same `useEffect`/`useState`/`isLoading` pattern, each slightly different, none cancelling inflight requests, all re-fetching on every mount.

TanStack Query eliminates this entirely. Every data source is a typed query with consistent semantics:

```typescript
// hooks/use-sentinel-data.ts

export function useRiskSummary() {
  return useQuery({
    queryKey: queryKeys.riskSummary,
    queryFn: () => dashboardApi.get<RiskSummary>("risk/summary"),
    staleTime: 30_000,
    refetchInterval: 60_000, // Live operational data — auto-refresh every minute
  });
}

export function useActorRiskProfile(actorId: string) {
  return useQuery({
    queryKey: queryKeys.actorProfile(actorId),
    queryFn: () => dashboardApi.get<ActorRiskProfile>(`risk/actors/${actorId}`),
    staleTime: 60_000,
    enabled: !!actorId,
  });
}

export function useComplianceReport(id: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.complianceReport(id),
    queryFn: () => dashboardApi.get<ComplianceReport>(`compliance/reports/${id}`),
    refetchInterval: (query) => {
      // Poll every 5s while the report is generating, stop when done
      const status = query.state.data?.status;
      return (status === "pending" || status === "generating") ? 5_000 : false;
    },
    enabled: !!id && enabled,
  });
}
```

Stale times are tuned per data type — not a global setting:

| Data | Stale Time | Reason |
|---|---|---|
| Risk summary | 30s | Live operational — stale data misses active incidents |
| Alerts | 60s | Actioned items — second or two of lag is fine |
| Audit events | 2min | Historical — doesn't change |
| Actor profile | 60s | Derived from events — changes slowly |
| Compliance reports | 10s | Polling while generating |

Mutations update the cache optimistically via `setQueryData` and invalidate the broader list:

```typescript
export function useAcknowledgeAlert() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (alertId: string) =>
      dashboardApi.post<AlertDetail>(`alerts/${alertId}/acknowledge`),
    onSuccess: (data) => {
      client.setQueryData(queryKeys.alertDetail(data.id), data);
      client.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
}
```

The analyst clicks "Acknowledge" in the alert inbox. The row updates immediately. The alert detail view is also updated. No page reload.

---

## The Actor Timeline: The Investigation View

The most important page in the dashboard is not the overview. It's `/actors/[id]` — the view that answers "what did this actor do."

It combines three data sources:

```typescript
// Actor timeline — server fetches in parallel via TanStack Query
const { data: profile } = useActorRiskProfile(actorId);
const { data: eventsPage } = useAuditEvents({ actor_id: actorId });
```

The risk score history renders in Recharts — a simple line chart with the last N scored events:

```typescript
const chartData = profile.recent_events
  .filter(e => e.risk_score !== null)
  .map(e => ({
    time: format(new Date(e.created_at), "HH:mm"),
    score: e.risk_score,
  }))
  .reverse(); // Chronological order for the chart

<LineChart data={chartData}>
  <YAxis domain={[0, 100]} />
  <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} />
  <Tooltip contentStyle={{ background: "#111827", ... }} />
</LineChart>
```

Below the chart: the full event log, paginated, with timestamps, event types, resource identifiers, and risk scores rendered as color-coded badges. The analyst can scan the timeline the way you'd read a court transcript — sequentially, with risk context on every line.

This view works identically for a human user (`actor_id` from their User record) and an AI agent (`actor_id` from their API key). The actor type label at the top changes; the investigation experience is the same.

---

## Compliance Reports: AI Attribution as the Headline

The compliance report service on the backend generates in three formats. The PDF is the one that matters for actual audits — it's what gets attached to a SOC 2 evidence package.

The key design decision: actor type breakdown is the first section after the header, not buried in appendices:

```python
# services.py — summary built before rendering
def _build_summary(self, events: QuerySet) -> dict:
    by_actor_type = dict(
        events.values("actor_type")
        .annotate(count=Count("id"))
        .values_list("actor_type", "count")
    )

    # The AI-attribution-forward section
    ai_agents = list(
        events.exclude(agent_name="")
        .filter(actor_type="AI_AGENT")
        .values("agent_name")
        .annotate(event_count=Count("id"))
        .order_by("-event_count")
    )

    return {
        "total_events": events.count(),
        "by_actor_type": by_actor_type,       # {"HUMAN": 1240, "AI_AGENT": 8903, "SERVICE": 445}
        "ai_agents_involved": ai_agents,       # [{"agent_name": "support-bot-v2", "event_count": 8903}]
        "high_risk_event_count": events.filter(risk_score__gte=50).count(),
    }
```

In the PDF, this renders as the first table after the header — "Activity by Actor Type" — followed immediately by "AI Agents Involved" if any AI agent events occurred in the period. An auditor opening the PDF sees within five seconds whether AI agents were active and which ones.

The report generation is async — Celery task with a 10-minute time limit for large datasets. The dashboard polls the report status every 5 seconds using the same TanStack Query `refetchInterval` pattern:

```typescript
// Compliance page — live polling card
const { data: report } = useComplianceReport(pollingId);

// TanStack Query stops polling automatically when status changes
refetchInterval: (query) => {
  const status = query.state.data?.status;
  if (status === "pending" || status === "generating") return 5_000;
  return false; // Stop polling — download link appears
},
```

The analyst requests a report, sees a spinner card, and within seconds to minutes (depending on the date range) the card flips to a green "Ready — Download" state. The download link hits the Django backend directly through the BFF proxy, which returns the file as a `FileResponse` with the correct `Content-Disposition` header.

---

## Current Full API + Dashboard Surface

**Backend:**
```
# Auth (Phase 2)
POST   /api/v1/auth/register/
POST   /api/v1/auth/login/
POST   /api/v1/auth/refresh/
POST   /api/v1/auth/logout/
GET    /api/v1/auth/me/
POST   /api/v1/auth/me/password/

# Audit (Phase 2)
POST/GET  /api/v1/events/ingest/
GET       /api/v1/events/
GET       /api/v1/events/{id}/
GET       /api/v1/events/{id}/verify/

# Risk & Alerts (Phase 3)
GET/POST  /api/v1/alerts/
GET/POST  /api/v1/alerts/rules/
DELETE    /api/v1/alerts/rules/{id}/
GET       /api/v1/alerts/{id}/
POST      /api/v1/alerts/{id}/acknowledge/
POST      /api/v1/alerts/{id}/resolve/
GET       /api/v1/risk/summary/
GET       /api/v1/risk/actors/{actor_id}/

# API Keys (Phase 3)
GET       /api/v1/api-keys/
POST      /api/v1/api-keys/create/
GET/DELETE /api/v1/api-keys/{id}/

# Compliance (Phase 4)
GET/POST  /api/v1/compliance/reports/
GET       /api/v1/compliance/reports/{id}/
GET       /api/v1/compliance/reports/{id}/download/
```

**Dashboard:**
```
/login              Auth form (httpOnly cookie BFF)
/dashboard          Overview: risk stats, open alerts, top risky AI agents
/alerts             Alert inbox: filters, ack/resolve inline
/actors/[id]        Actor timeline: risk chart + full event log
/ai-agents          Registered AI agents + recent activity
/api-keys           Key management: create (AI agent + service), revoke
/compliance         Report request, polling card, download
```

---

## What's Next

Phase 5 is multi-tenancy and Kafka — the infrastructure that takes Sentinel from a single-organization deployment to a shared platform, and from synchronous risk scoring to event-driven stream processing.

The architecture designed in Phase 1 (service/repository separation, abstracted task interfaces, cursor-based pagination, no hardcoded assumptions about single-tenant operation) was built to support this. Adding tenant isolation at the row level, replacing Celery's Redis broker with Kafka topics, and deploying to Kubernetes are all additive changes — not rewrites.

---

*Star the repo: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*

*v0.4.0 tagged. Phase 5 in progress.*
