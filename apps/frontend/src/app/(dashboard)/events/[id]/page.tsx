"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/dashboard-api";
import { formatActorLabel, type AuditEvent } from "@/types/dashboard";

export default function AuditEventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const {
    data: event,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["events", id],
    queryFn: () => dashboardApi.get<AuditEvent>(`events/${id}`),
  });

  if (isLoading) return <p className="p-6 text-gray-400">Loading event…</p>;
  if (error || !event)
    return (
      <p role="alert" className="p-6 text-red-400">
        Unable to load event: {error?.message ?? "Not found"}
      </p>
    );

  return (
    <div className="space-y-5 p-6">
      <Link href="/events" className="text-sm text-sentinel-400">
        ← Audit Log
      </Link>
      <h1 className="text-xl font-semibold text-white">{event.event_type}</h1>
      <p className="text-gray-400">{formatActorLabel(event)}</p>
      <dl className="grid gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 sm:grid-cols-2">
        {Object.entries({
          "Risk score": event.risk_score ?? "Pending Kafka processing",
          "Resource type": event.resource_type,
          "Resource ID": event.resource_id,
          "Recorded at": event.created_at,
          "Actor IP": event.actor_ip ?? "Unavailable",
          "Request ID": event.request_id,
        }).map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-gray-500">{label}</dt>
            <dd className="mt-1 break-all text-sm text-white">
              {value || "—"}
            </dd>
          </div>
        ))}
      </dl>
      {event.actor_id && (
        <Link
          href={`/actors/${event.actor_id}`}
          className="inline-block text-sm text-sentinel-400"
        >
          View actor timeline →
        </Link>
      )}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
        <h2 className="mb-3 font-medium text-white">Event metadata</h2>
        {event.metadata.demo_data === true && (
          <p className="mb-3 text-sm text-sentinel-400">Synthetic demo data</p>
        )}
        <pre className="overflow-x-auto whitespace-pre-wrap break-all text-sm text-gray-300">
          {JSON.stringify(event.metadata, null, 2)}
        </pre>
      </div>
    </div>
  );
}
