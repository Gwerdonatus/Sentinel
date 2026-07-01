"use client";

import { useAPIKeys } from "@/hooks/use-sentinel-data";
import { useAuditEvents } from "@/hooks/use-sentinel-data";
import { formatDistanceToNow } from "date-fns";
import Link from "next/link";
import { getRiskLevel, RISK_LEVEL_BG } from "@/types/dashboard";

export default function AIAgentsPage() {
  const { data: keys, isLoading: keysLoading } = useAPIKeys();
  const { data: recentEvents, isLoading: eventsLoading } = useAuditEvents({
    actor_type: "AI_AGENT",
  });

  const aiKeys = keys?.filter((k) => k.actor_type === "AI_AGENT") ?? [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">AI Agents</h1>
        <p className="mt-0.5 text-sm text-gray-400">
          Registered AI agents and their recent activity
        </p>
      </div>

      {/* Registered agents */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Registered Agents</h2>
        </div>
        {keysLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800" />
            ))}
          </div>
        ) : aiKeys.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <p className="text-sm text-gray-500">No AI agent keys registered yet.</p>
            <p className="mt-1 text-xs text-gray-600">
              Create an API key with actor_type=AI_AGENT to register an agent.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {aiKeys.map((key) => (
              <div key={key.id} className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-900/40 text-xl">
                      🤖
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-white">{key.agent_name || key.name}</p>
                        {key.agent_version && (
                          <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400">
                            {key.agent_version}
                          </span>
                        )}
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${
                            key.is_active
                              ? "bg-green-900/30 text-green-400"
                              : "bg-gray-800 text-gray-500"
                          }`}
                        >
                          {key.is_active ? "active" : "inactive"}
                        </span>
                      </div>
                      {key.agent_description && (
                        <p className="mt-0.5 text-xs text-gray-500 line-clamp-1">
                          {key.agent_description}
                        </p>
                      )}
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {key.scopes.map((scope) => (
                          <span
                            key={scope}
                            className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-xs text-gray-400"
                          >
                            {scope}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="shrink-0 text-right text-xs text-gray-500">
                    <p>{key.total_uses.toLocaleString()} requests</p>
                    {key.last_used_at && (
                      <p className="mt-0.5">
                        Last:{" "}
                        {formatDistanceToNow(new Date(key.last_used_at), { addSuffix: true })}
                      </p>
                    )}
                    <Link
                      href={`/actors/${key.id}`}
                      className="mt-1 block text-sentinel-400 hover:text-sentinel-300"
                    >
                      View timeline →
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent AI agent events */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Recent AI Agent Events</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Event</th>
                <th className="px-4 py-3 font-medium">Resource</th>
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="px-4 py-3 font-medium">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {eventsLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 animate-pulse rounded bg-gray-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : recentEvents?.results.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-600">
                    No AI agent events found
                  </td>
                </tr>
              ) : (
                recentEvents?.results.map((event) => {
                  const level = getRiskLevel(event.risk_score);
                  return (
                    <tr key={event.id} className="hover:bg-gray-800/20">
                      <td className="px-4 py-3 font-medium text-white">
                        {event.agent_name || "—"}
                      </td>
                      <td className="px-4 py-3 text-gray-300">{event.event_type}</td>
                      <td className="px-4 py-3 text-gray-500">
                        {event.resource_type || "—"}
                        {event.resource_id && (
                          <span className="ml-1 font-mono text-xs text-gray-600">
                            {event.resource_id.slice(0, 12)}…
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {event.risk_score !== null ? (
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${RISK_LEVEL_BG[level]}`}
                          >
                            {event.risk_score}
                          </span>
                        ) : (
                          <span className="text-gray-600">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
