"use client";

import { useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import { useAuditEvents } from "@/hooks/use-sentinel-data";
import {
  formatActorLabel,
  getRiskLevel,
  RISK_LEVEL_BG,
} from "@/types/dashboard";

export default function AuditLogPage() {
  const [actorType, setActorType] = useState("");
  const [cursor, setCursor] = useState("");
  const filters: Record<string, string> = {};
  if (actorType) filters.actor_type = actorType;
  if (cursor) filters.cursor = cursor;
  const { data, isLoading, error } = useAuditEvents(filters);

  function navigate(url: string | null) {
    if (url)
      setCursor(
        new URL(url, window.location.origin).searchParams.get("cursor") ?? "",
      );
  }

  return (
    <div className="space-y-5 p-6">
      <h1 className="text-xl font-semibold text-white">Audit Log</h1>
      <p className="text-sm text-gray-400">
        Signed audit events and their computed risk scores
      </p>
      <select
        aria-label="Actor type"
        value={actorType}
        onChange={(e) => {
          setActorType(e.target.value);
          setCursor("");
        }}
        className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm"
      >
        <option value="">All actors</option>
        <option value="AI_AGENT">AI agents</option>
        <option value="HUMAN">Humans</option>
        <option value="SERVICE">Services</option>
      </select>
      {error && (
        <p role="alert" className="text-red-400">
          Unable to load events: {error.message}
        </p>
      )}
      {isLoading && <p className="text-gray-400">Loading events…</p>}
      <div className="divide-y divide-gray-800 rounded-xl border border-gray-800 bg-gray-900/50">
        {data?.results.map((event) => (
          <Link
            key={event.id}
            href={`/events/${event.id}`}
            className="flex items-start justify-between gap-4 px-5 py-4 hover:bg-gray-800/40"
          >
            <div className="min-w-0">
              <p className="font-medium text-white">{event.event_type}</p>
              <p className="text-sm text-gray-400">{formatActorLabel(event)}</p>
              <p className="break-all text-xs text-gray-500">
                {event.resource_type} · {event.resource_id}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                {format(new Date(event.created_at), "MMM d, yyyy HH:mm:ss")}
              </p>
            </div>
            <span
              className={`shrink-0 rounded-full px-2 py-1 text-xs ${RISK_LEVEL_BG[getRiskLevel(event.risk_score)]}`}
            >
              {event.risk_score ?? "Pending"}
            </span>
          </Link>
        ))}
        {data?.results.length === 0 && (
          <p className="p-5 text-gray-400">No events match this filter.</p>
        )}
      </div>
      {data && (
        <div className="flex justify-between">
          <button
            disabled={!data.pagination.previous}
            onClick={() => navigate(data.pagination.previous)}
            className="text-sm text-sentinel-400 disabled:opacity-30"
          >
            ← Previous
          </button>
          <button
            disabled={!data.pagination.next}
            onClick={() => navigate(data.pagination.next)}
            className="text-sm text-sentinel-400 disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
