"use client";

import { use } from "react";
import { useActorRiskProfile, useAuditEvents } from "@/hooks/use-sentinel-data";
import { formatDistanceToNow, format } from "date-fns";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  ACTOR_TYPE_ICONS, getRiskLevel, RISK_LEVEL_BG, type AuditEvent,
} from "@/types/dashboard";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function ActorTimelinePage({ params }: PageProps) {
  const { id: actorId } = use(params);

  const { data: profile, isLoading: profileLoading } = useActorRiskProfile(actorId);
  const { data: eventsPage, isLoading: eventsLoading } = useAuditEvents({ actor_id: actorId });

  if (profileLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-sentinel-500 border-t-transparent" />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-500">
        Actor not found or no events in the last 30 days.
      </div>
    );
  }

  const actorLabel =
    profile.agent_name ? `🤖 ${profile.agent_name}` :
    profile.actor_email ? `👤 ${profile.actor_email}` :
    `⚙️ ${profile.actor_type}`;

  // Risk score chart data — plot the last 10 events with scores
  const chartData = profile.recent_events
    .filter((e) => e.risk_score !== null)
    .map((e) => ({
      time: format(new Date(e.created_at), "HH:mm"),
      score: e.risk_score,
      event_type: e.event_type,
    }))
    .reverse();

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm text-gray-500">
            <span>{ACTOR_TYPE_ICONS[profile.actor_type]}</span>
            <span className="uppercase tracking-wider text-xs">{profile.actor_type}</span>
          </div>
          <h1 className="text-xl font-semibold text-white">{actorLabel}</h1>
          <p className="mt-0.5 font-mono text-xs text-gray-600">{actorId}</p>
        </div>
        {profile.last_30_days.open_alerts > 0 && (
          <div className="rounded-lg border border-red-800 bg-red-900/20 px-4 py-2 text-sm font-medium text-red-400">
            {profile.last_30_days.open_alerts} open alert{profile.last_30_days.open_alerts > 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Events (30d)", value: profile.last_30_days.total_events },
          { label: "Avg Risk Score", value: profile.last_30_days.avg_risk_score.toFixed(1) },
          { label: "Max Risk Score", value: profile.last_30_days.max_risk_score },
          { label: "Open Alerts", value: profile.last_30_days.open_alerts },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="mt-1 text-2xl font-bold tabular text-white">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Risk score chart */}
      {chartData.length > 1 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
          <h2 className="mb-4 text-sm font-semibold text-white">Risk Score History</h2>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#6b7280" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#6b7280" }} width={28} />
              <Tooltip
                contentStyle={{ background: "#111827", border: "1px solid #374151", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#9ca3af" }}
                itemStyle={{ color: "#a5b4fc" }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ fill: "#6366f1", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Event timeline */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Event Timeline</h2>
        </div>
        <div className="divide-y divide-gray-800/50">
          {eventsLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-5 py-3">
                <div className="h-4 w-32 animate-pulse rounded bg-gray-800" />
                <div className="h-4 flex-1 animate-pulse rounded bg-gray-800/60" />
              </div>
            ))
          ) : eventsPage?.results.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-600">No events found</div>
          ) : (
            eventsPage?.results.map((event) => (
              <EventRow key={event.id} event={event} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function EventRow({ event }: { event: AuditEvent }) {
  const level = getRiskLevel(event.risk_score);
  return (
    <div className="flex items-start gap-4 px-5 py-3">
      <div className="shrink-0 w-32 text-xs text-gray-500 tabular pt-0.5">
        {format(new Date(event.created_at), "MMM d, HH:mm:ss")}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">{event.event_type}</span>
          {event.resource_type && (
            <span className="text-xs text-gray-500">→ {event.resource_type}</span>
          )}
        </div>
        {event.resource_id && (
          <p className="mt-0.5 font-mono text-xs text-gray-600 truncate">{event.resource_id}</p>
        )}
      </div>
      {event.risk_score !== null && (
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${RISK_LEVEL_BG[level]}`}>
          {event.risk_score}
        </span>
      )}
    </div>
  );
}
