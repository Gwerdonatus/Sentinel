"use client";

import { useRiskSummary, useAlerts } from "@/hooks/use-sentinel-data";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import { SEVERITY_COLORS, type AlertListItem } from "@/types/dashboard";

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useRiskSummary();
  const { data: alertsPage, isLoading: alertsLoading } = useAlerts({ status: "open" });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <p className="mt-0.5 text-sm text-gray-400">
          Real-time risk intelligence across all actors
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Open Alerts"
          value={summary?.open_alerts.total ?? "—"}
          sub={`${summary?.open_alerts.critical ?? 0} critical`}
          loading={summaryLoading}
          accent="red"
        />
        <StatCard
          label="Events (24h)"
          value={summary?.last_24h.total_events ?? "—"}
          sub={`${summary?.last_24h.ai_agent_events ?? 0} from AI agents`}
          loading={summaryLoading}
          accent="blue"
        />
        <StatCard
          label="High-Risk Events"
          value={summary?.last_24h.high_risk_events ?? "—"}
          sub="Score ≥ 50 in last 24h"
          loading={summaryLoading}
          accent="orange"
        />
        <StatCard
          label="New Alerts (24h)"
          value={summary?.last_24h.new_alerts ?? "—"}
          sub="Across all rules"
          loading={summaryLoading}
          accent="purple"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Open alerts */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50">
          <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Open Alerts</h2>
            <Link href="/alerts" className="text-xs text-sentinel-400 hover:text-sentinel-300">
              View all →
            </Link>
          </div>
          <div className="divide-y divide-gray-800/50">
            {alertsLoading ? (
              <LoadingRows count={4} />
            ) : alertsPage?.results.length === 0 ? (
              <EmptyState message="No open alerts" />
            ) : (
              alertsPage?.results.slice(0, 6).map((alert) => (
                <AlertRow key={alert.id} alert={alert} />
              ))
            )}
          </div>
        </div>

        {/* Top risky AI agents */}
        <div className="rounded-xl border border-gray-800 bg-gray-900/50">
          <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
            <h2 className="text-sm font-semibold text-white">Top Risky AI Agents (24h)</h2>
            <Link href="/ai-agents" className="text-xs text-sentinel-400 hover:text-sentinel-300">
              View all →
            </Link>
          </div>
          <div className="divide-y divide-gray-800/50">
            {summaryLoading ? (
              <LoadingRows count={4} />
            ) : !summary?.top_risky_ai_agents.length ? (
              <EmptyState message="No AI agent anomalies detected" />
            ) : (
              summary.top_risky_ai_agents.map((agent) => (
                <div key={agent.agent_name} className="flex items-center justify-between px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-base">🤖</span>
                    <span className="text-sm text-white">{agent.agent_name}</span>
                  </div>
                  <span className="rounded-full bg-red-900/30 px-2 py-0.5 text-xs font-medium text-red-400">
                    {agent.event_count} events
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Alert severity breakdown */}
      {summary && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
          <h2 className="mb-4 text-sm font-semibold text-white">Open Alert Severity Breakdown</h2>
          <div className="grid grid-cols-4 gap-3">
            {(["critical", "high", "medium", "low"] as const).map((sev) => (
              <div
                key={sev}
                className={`rounded-lg border px-4 py-3 text-center ${SEVERITY_COLORS[sev]}`}
              >
                <div className="text-2xl font-bold tabular">{summary.open_alerts[sev]}</div>
                <div className="mt-0.5 text-xs capitalize opacity-80">{sev}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Sub-components
// =============================================================================

function StatCard({
  label, value, sub, loading, accent,
}: {
  label: string;
  value: number | string;
  sub: string;
  loading: boolean;
  accent: "red" | "blue" | "orange" | "purple";
}) {
  const accentClasses = {
    red: "text-red-400",
    blue: "text-sentinel-400",
    orange: "text-orange-400",
    purple: "text-purple-400",
  };

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
      <p className="text-xs text-gray-500">{label}</p>
      {loading ? (
        <div className="mt-1 h-8 w-16 animate-pulse rounded bg-gray-800" />
      ) : (
        <p className={`mt-1 text-3xl font-bold tabular ${accentClasses[accent]}`}>{value}</p>
      )}
      <p className="mt-1 text-xs text-gray-600">{sub}</p>
    </div>
  );
}

function AlertRow({ alert }: { alert: AlertListItem }) {
  return (
    <Link href={`/alerts/${alert.id}`} className="block px-5 py-3 transition-colors hover:bg-gray-800/30">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`rounded-full border px-1.5 py-0.5 text-xs ${SEVERITY_COLORS[alert.severity]}`}>
              {alert.severity}
            </span>
            {alert.agent_name && (
              <span className="text-xs text-gray-500">🤖 {alert.agent_name}</span>
            )}
          </div>
          <p className="mt-1 truncate text-sm text-white">{alert.rule_name}</p>
          <p className="text-xs text-gray-500">
            {alert.actor_email || alert.actor_type}
          </p>
        </div>
        <span className="shrink-0 text-xs text-gray-600">
          {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
        </span>
      </div>
    </Link>
  );
}

function LoadingRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="px-5 py-3">
          <div className="h-4 w-2/3 animate-pulse rounded bg-gray-800" />
          <div className="mt-1.5 h-3 w-1/3 animate-pulse rounded bg-gray-800/60" />
        </div>
      ))}
    </>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="px-5 py-8 text-center text-sm text-gray-600">{message}</div>
  );
}
