"use client";

import { use } from "react";
import Link from "next/link";
import { useAlertDetail } from "@/hooks/use-sentinel-data";
import { SEVERITY_COLORS, STATUS_COLORS } from "@/types/dashboard";

export default function AlertDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: alert, isLoading, error } = useAlertDetail(id);

  if (isLoading) return <p className="p-6 text-gray-400">Loading alert…</p>;
  if (error || !alert)
    return (
      <p role="alert" className="p-6 text-red-400">
        Unable to load alert: {error?.message ?? "Not found"}
      </p>
    );

  return (
    <div className="space-y-5 p-6">
      <Link href="/alerts" className="text-sm text-sentinel-400">
        ← Alert Inbox
      </Link>
      <h1 className="text-xl font-semibold text-white">{alert.rule_name}</h1>
      <div className="flex gap-3">
        <span
          className={`rounded-full border px-3 py-1 text-sm ${SEVERITY_COLORS[alert.severity]}`}
        >
          {alert.severity}
        </span>
        <span className={`py-1 text-sm ${STATUS_COLORS[alert.status]}`}>
          {alert.status}
        </span>
      </div>
      <dl className="grid gap-4 rounded-xl border border-gray-800 bg-gray-900/50 p-5 sm:grid-cols-2">
        {Object.entries({
          Actor: alert.agent_name || alert.actor_email || alert.actor_type,
          "Actor type": alert.actor_type,
          "Risk score": alert.risk_score ?? "Pending",
          "Detected at": alert.created_at,
        }).map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-gray-500">{label}</dt>
            <dd className="mt-1 break-all text-sm text-white">{value}</dd>
          </div>
        ))}
      </dl>
      <section className="rounded-xl border border-gray-800 bg-gray-900/50 p-5">
        <h2 className="mb-3 font-medium text-white">Risk explanation</h2>
        <p className="text-sm text-gray-300">
          {alert.risk_explanation || "No explanation recorded."}
        </p>
      </section>
      <div className="flex flex-wrap gap-5">
        <Link
          href={`/events/${alert.audit_event_id}`}
          className="text-sm text-sentinel-400"
        >
          View triggering audit event →
        </Link>
        {alert.actor_id && (
          <Link
            href={`/actors/${alert.actor_id}`}
            className="text-sm text-sentinel-400"
          >
            View actor timeline →
          </Link>
        )}
      </div>
      {alert.resolution_note && (
        <p className="text-sm text-gray-300">
          Resolution: {alert.resolution_note}
        </p>
      )}
    </div>
  );
}
