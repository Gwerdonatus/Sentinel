"use client";

import { useState } from "react";
import { useAlerts, useAcknowledgeAlert, useResolveAlert } from "@/hooks/use-sentinel-data";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import {
  SEVERITY_COLORS, STATUS_COLORS, ACTOR_TYPE_ICONS,
  type AlertSeverity, type AlertStatus,
} from "@/types/dashboard";

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "resolved", label: "Resolved" },
];

const SEVERITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All severities" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const ACTOR_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "All actors" },
  { value: "AI_AGENT", label: "🤖 AI Agents" },
  { value: "HUMAN", label: "👤 Humans" },
  { value: "SERVICE", label: "⚙️ Services" },
];

export default function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState("open");
  const [severityFilter, setSeverityFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");

  const filters: Record<string, string> = {};
  if (statusFilter) filters.status = statusFilter;
  if (severityFilter) filters.severity = severityFilter;
  if (actorFilter) filters.actor_type = actorFilter;

  const { data, isLoading } = useAlerts(filters);
  const acknowledge = useAcknowledgeAlert();
  const resolve = useResolveAlert();

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-white">Alert Inbox</h1>
        <p className="mt-0.5 text-sm text-gray-400">
          Investigate and action security alerts across all actor types
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={statusFilter} onChange={setStatusFilter} options={STATUS_OPTIONS} />
        <Select value={severityFilter} onChange={setSeverityFilter} options={SEVERITY_OPTIONS} />
        <Select value={actorFilter} onChange={setActorFilter} options={ACTOR_OPTIONS} />
      </div>

      {/* Alert table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                <th className="px-4 py-3 font-medium">Severity</th>
                <th className="px-4 py-3 font-medium">Rule</th>
                <th className="px-4 py-3 font-medium">Actor</th>
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 w-full animate-pulse rounded bg-gray-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : data?.results.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-gray-600">
                    No alerts match the current filters
                  </td>
                </tr>
              ) : (
                data?.results.map((alert) => (
                  <tr key={alert.id} className="hover:bg-gray-800/20">
                    <td className="px-4 py-3">
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${SEVERITY_COLORS[alert.severity as AlertSeverity]}`}>
                        {alert.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/alerts/${alert.id}`} className="font-medium text-white hover:text-sentinel-400">
                        {alert.rule_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        <span>{ACTOR_TYPE_ICONS[alert.actor_type]}</span>
                        <span className="text-gray-300">
                          {alert.agent_name || alert.actor_email || alert.actor_type}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {alert.risk_score !== null ? (
                        <RiskScoreBadge score={alert.risk_score} />
                      ) : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-medium ${STATUS_COLORS[alert.status as AlertStatus]}`}>
                        {alert.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1.5">
                        {alert.status === "open" && (
                          <ActionButton
                            label="Ack"
                            onClick={() => acknowledge.mutate(alert.id)}
                            loading={acknowledge.isPending}
                          />
                        )}
                        {alert.status !== "resolved" && (
                          <ActionButton
                            label="Resolve"
                            onClick={() => resolve.mutate({ alertId: alert.id })}
                            loading={resolve.isPending}
                          />
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && (data.pagination.next || data.pagination.previous) && (
          <div className="flex justify-between border-t border-gray-800 px-4 py-3">
            <button
              disabled={!data.pagination.previous}
              className="text-xs text-gray-500 hover:text-white disabled:opacity-30"
            >
              ← Previous
            </button>
            <button
              disabled={!data.pagination.next}
              className="text-xs text-gray-500 hover:text-white disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Select({
  value, onChange, options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

function RiskScoreBadge({ score }: { score: number }) {
  const color =
    score >= 75 ? "text-red-400" :
    score >= 50 ? "text-orange-400" :
    score >= 25 ? "text-yellow-400" : "text-green-400";
  return (
    <span className={`font-mono tabular text-sm font-semibold ${color}`}>{score}</span>
  );
}

function ActionButton({
  label, onClick, loading,
}: {
  label: string;
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="rounded border border-gray-700 px-2 py-0.5 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-white disabled:opacity-40"
    >
      {label}
    </button>
  );
}
