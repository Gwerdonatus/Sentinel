"use client";
import Link from "next/link";
import {
  ArrowUpRight,
  Bell,
  Activity,
  ScanEye,
  RefreshCw,
  ArrowRight,
  Fingerprint,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import {
  useRiskSummary,
  useAlerts,
  useAuditEvents,
} from "@/hooks/use-sentinel-data";
import { SEVERITY_COLORS } from "@/types/dashboard";

export default function DashboardPage() {
  const summaryQuery = useRiskSummary();
  const alertsQuery = useAlerts({ status: "open" });
  const eventsQuery = useAuditEvents();
  const summary = summaryQuery.data;
  const busy =
    summaryQuery.isFetching || alertsQuery.isFetching || eventsQuery.isFetching;
  function refresh() {
    void summaryQuery.refetch();
    void alertsQuery.refetch();
    void eventsQuery.refetch();
  }
  const failed =
    summaryQuery.isError || alertsQuery.isError || eventsQuery.isError;
  return (
    <div className="overview-page">
      <div className="overview-heading">
        <div>
          <div className="eyebrow">YOUR SECURITY PERSPECTIVE</div>
          <h1>A clearer view.</h1>
          <p>
            Every actor. Every signal. Everything that needs your attention.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={busy}
          className="button button-white"
        >
          <RefreshCw size={15} className={busy ? "animate-spin" : ""} />
          {busy ? "Updating…" : "Refresh"}
        </button>
      </div>
      {failed && (
        <div role="alert" className="error-banner">
          Some workspace data could not be loaded. Refresh to try again.
        </div>
      )}
      <section className="attention-banner">
        <div className="attention-icon">
          <ScanEye size={26} strokeWidth={1.5} />
        </div>
        <div>
          <h2>
            {summary
              ? summary.open_alerts.total
                ? `${summary.open_alerts.total} signals need your attention.`
                : "Your alert inbox is clear."
              : "Reading your security signals…"}
          </h2>
          <p>
            {summary
              ? `${summary.open_alerts.high} high-severity alerts · ${summary.open_alerts.critical} critical alerts`
              : "Fetching the latest risk intelligence"}
          </p>
        </div>
        <Link href="/alerts" className="button button-dark">
          Review alerts <ArrowRight size={16} />
        </Link>
      </section>
      <div className="metric-grid">
        {[
          {
            label: "Open alerts",
            value: summary?.open_alerts.total,
            sub: "Awaiting investigation",
            icon: Bell,
            href: "/alerts",
            color: "coral",
          },
          {
            label: "Events observed",
            value: summary?.last_24h.total_events,
            sub: "In the last 24 hours",
            icon: Activity,
            href: "/events",
            color: "blue",
          },
          {
            label: "High-risk events",
            value: summary?.last_24h.high_risk_events,
            sub: "Risk score of 50 or above · 24h",
            icon: ScanEye,
            href: "/events",
            color: "amber",
          },
          {
            label: "AI agent activity",
            value: summary?.last_24h.ai_agent_events,
            sub: "Attributed events · last 24h",
            icon: Fingerprint,
            href: "/ai-agents",
            color: "violet",
          },
        ].map(({ icon: Icon, ...m }) => (
          <Link
            href={m.href}
            className={`metric-card ${m.color}`}
            key={m.label}
          >
            <div>
              <span>{m.label}</span>
              <Icon size={18} strokeWidth={1.5} />
            </div>
            <strong>{m.value ?? "—"}</strong>
            <p>
              {m.sub}
              <ArrowUpRight size={14} />
            </p>
          </Link>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel priority-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">PRIORITY INBOX</div>
              <h2>Worth a closer look.</h2>
            </div>
            <Link href="/alerts">
              View all <ArrowUpRight size={15} />
            </Link>
          </div>
          {alertsQuery.isLoading ? (
            <p className="panel-empty" role="status">
              Loading alerts…
            </p>
          ) : alertsQuery.data?.results.length ? (
            alertsQuery.data.results.slice(0, 4).map((a) => (
              <Link
                href={`/alerts/${a.id}`}
                className="priority-row"
                key={a.id}
              >
                <span className="alert-glyph">
                  <Bell size={18} />
                </span>
                <div>
                  <span
                    className={`severity-pill ${SEVERITY_COLORS[a.severity]}`}
                  >
                    {a.severity}
                  </span>
                  <h3>{a.rule_name}</h3>
                  <p>
                    {a.agent_name || a.actor_email || a.actor_type}{" "}
                    <span>·</span>{" "}
                    {formatDistanceToNow(new Date(a.created_at), {
                      addSuffix: true,
                    })}
                  </p>
                </div>
                <ArrowUpRight className="row-arrow" size={17} />
              </Link>
            ))
          ) : (
            <p className="panel-empty">
              {alertsQuery.isError
                ? "Alerts unavailable"
                : "No open alerts. You’re up to date."}
            </p>
          )}
        </section>
        <section className="panel severity-panel">
          <div className="panel-heading">
            <div>
              <div className="eyebrow">OPEN ALERTS</div>
              <h2>The risk picture.</h2>
            </div>
            <span className="period-label">Current</span>
          </div>
          <div className="severity-summary">
            <strong>{summary?.open_alerts.total ?? "—"}</strong>
            <span>signals to investigate</span>
          </div>
          <div className="severity-list">
            {(["critical", "high", "medium", "low"] as const).map((s) => (
              <div key={s}>
                <span>
                  <i className={`severity-dot ${s}`} />
                  {s}
                </span>
                <strong>{summary?.open_alerts[s] ?? "—"}</strong>
              </div>
            ))}
          </div>
          <Link href="/alerts" className="panel-bottom-link">
            Open alert inbox <ArrowRight size={16} />
          </Link>
        </section>
      </div>
      <section className="panel recent-panel">
        <div className="panel-heading">
          <div>
            <div className="eyebrow">AUDIT TRAIL</div>
            <h2>Recent activity.</h2>
          </div>
          <Link href="/events">
            Explore events <ArrowUpRight size={15} />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="activity-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Actor</th>
                <th>Resource</th>
                <th>Risk score</th>
                <th>Recorded</th>
              </tr>
            </thead>
            <tbody>
              {eventsQuery.data?.results.slice(0, 5).map((e) => (
                <tr key={e.id}>
                  <td>
                    <Link href={`/events/${e.id}`}>
                      {e.event_type.replaceAll("_", " ")}
                      <ArrowUpRight size={13} />
                    </Link>
                    {e.metadata.demo_data === true && (
                      <small>Synthetic demo</small>
                    )}
                  </td>
                  <td>{e.agent_name || e.actor_email || e.actor_type}</td>
                  <td>{e.resource_type || "—"}</td>
                  <td>
                    <span
                      className={`score-chip ${(e.risk_score ?? 0) >= 50 ? "elevated" : ""}`}
                    >
                      {e.risk_score ?? "Pending"}
                    </span>
                  </td>
                  <td>
                    {formatDistanceToNow(new Date(e.created_at), {
                      addSuffix: true,
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!eventsQuery.data?.results.length && (
          <p className="panel-empty">
            {eventsQuery.isLoading
              ? "Loading recent activity…"
              : eventsQuery.isError
                ? "Activity unavailable"
                : "No events recorded yet."}
          </p>
        )}
      </section>
    </div>
  );
}
