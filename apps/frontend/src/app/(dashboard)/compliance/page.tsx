"use client";

import { useState } from "react";
import {
  useComplianceReports,
  useComplianceReport,
  useRequestComplianceReport,
} from "@/hooks/use-sentinel-data";
import { format } from "date-fns";
import type { ComplianceReport } from "@/types/dashboard";

export default function CompliancePage() {
  const { data: reports, isLoading } = useComplianceReports();
  const requestReport = useRequestComplianceReport();
  const [showForm, setShowForm] = useState(false);
  const [pollingId, setPollingId] = useState<string | null>(null);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Compliance Reports</h1>
          <p className="mt-0.5 text-sm text-gray-400">
            Generate evidence packages with AI actor attribution built in
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="rounded-lg bg-sentinel-600 px-4 py-2 text-sm font-medium text-white hover:bg-sentinel-500"
        >
          + Request Report
        </button>
      </div>

      {showForm && (
        <RequestReportForm
          onSubmit={async (payload) => {
            const report = await requestReport.mutateAsync(payload);
            setPollingId(report.id);
            setShowForm(false);
          }}
          onCancel={() => setShowForm(false)}
          isSubmitting={requestReport.isPending}
        />
      )}

      {/* Active polling card */}
      {pollingId && (
        <PendingReportCard
          reportId={pollingId}
          onDone={() => setPollingId(null)}
        />
      )}

      {/* Reports table */}
      <div className="rounded-xl border border-gray-800 bg-gray-900/50">
        <div className="border-b border-gray-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-white">Generated Reports</h2>
        </div>
        {isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-800" />
            ))}
          </div>
        ) : !reports?.length ? (
          <div className="px-5 py-10 text-center text-sm text-gray-600">
            No reports yet. Request one above.
          </div>
        ) : (
          <div className="divide-y divide-gray-800/50">
            {reports.map((report) => (
              <ReportRow key={report.id} report={report} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RequestReportForm({
  onSubmit,
  onCancel,
  isSubmitting,
}: {
  onSubmit: (payload: {
    report_type: string;
    report_format: string;
    from_dt: string;
    to_dt: string;
    filters: Record<string, string>;
  }) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}) {
  const [reportType, setReportType] = useState("soc2");
  const [reportFormat, setReportFormat] = useState("pdf");
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [toDate, setToDate] = useState(() => new Date().toISOString().slice(0, 10));

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-white">Request Compliance Report</h2>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Report Type</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
          >
            <option value="soc2">SOC 2 Evidence</option>
            <option value="pci_dss">PCI-DSS Evidence</option>
            <option value="custom">Custom Export</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Format</label>
          <select
            value={reportFormat}
            onChange={(e) => setReportFormat(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
          >
            <option value="pdf">PDF</option>
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">From</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">To</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white focus:border-sentinel-500 focus:outline-none"
          />
        </div>
      </div>

      <p className="rounded-lg border border-indigo-900/50 bg-indigo-950/30 px-4 py-3 text-xs text-indigo-300">
        🤖 AI actor attribution is included automatically in all Sentinel reports — human,
        service, and AI agent activity appears in separate sections with agent names and versions.
      </p>

      <div className="flex justify-end gap-3">
        <button onClick={onCancel} className="px-4 py-2 text-sm text-gray-400 hover:text-white">
          Cancel
        </button>
        <button
          onClick={() =>
            onSubmit({
              report_type: reportType,
              report_format: reportFormat,
              from_dt: `${fromDate}T00:00:00Z`,
              to_dt: `${toDate}T23:59:59Z`,
              filters: {},
            })
          }
          disabled={isSubmitting}
          className="rounded-lg bg-sentinel-600 px-4 py-2 text-sm font-medium text-white hover:bg-sentinel-500 disabled:opacity-40"
        >
          {isSubmitting ? "Requesting…" : "Generate Report"}
        </button>
      </div>
    </div>
  );
}

function PendingReportCard({ reportId, onDone }: { reportId: string; onDone: () => void }) {
  const { data: report } = useComplianceReport(reportId);

  if (!report) return null;

  if (report.status === "ready") {
    return (
      <div className="rounded-xl border border-green-800 bg-green-900/20 p-5">
        <p className="mb-3 text-sm font-semibold text-green-400">✓ Report ready</p>
        <div className="flex items-center gap-3">
          <a
            href={`/api/internal/proxy/compliance/reports/${report.id}/download`}
            download
            className="rounded-lg bg-green-800 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            Download {report.report_format.toUpperCase()}
          </a>
          <button onClick={onDone} className="text-sm text-gray-500 hover:text-gray-400">
            Dismiss
          </button>
        </div>
      </div>
    );
  }

  if (report.status === "failed") {
    return (
      <div className="rounded-xl border border-red-800 bg-red-900/20 p-5">
        <p className="text-sm font-semibold text-red-400">Report generation failed</p>
        <p className="mt-1 text-xs text-red-400/70">{report.error_message}</p>
        <button onClick={onDone} className="mt-2 text-xs text-gray-500 hover:text-gray-400">
          Dismiss
        </button>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-5">
      <div className="flex items-center gap-3">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-sentinel-500 border-t-transparent" />
        <p className="text-sm text-gray-300">
          {report.status === "pending" ? "Queued for generation…" : "Generating report…"}
        </p>
      </div>
    </div>
  );
}

function ReportRow({ report }: { report: ComplianceReport }) {
  const statusColors: Record<string, string> = {
    ready: "text-green-400",
    generating: "text-yellow-400",
    pending: "text-gray-400",
    failed: "text-red-400",
    expired: "text-gray-600",
  };

  return (
    <div className="flex items-center justify-between px-5 py-4">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">
            {report.report_type === "pci_dss"
              ? "PCI-DSS"
              : report.report_type === "soc2"
              ? "SOC 2"
              : "Custom"}{" "}
            Evidence
          </span>
          <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs uppercase text-gray-400">
            {report.report_format}
          </span>
          <span className={`text-xs font-medium ${statusColors[report.status] ?? "text-gray-500"}`}>
            {report.status}
          </span>
        </div>
        <p className="mt-0.5 text-xs text-gray-500">
          {format(new Date(report.from_dt), "MMM d, yyyy")} —{" "}
          {format(new Date(report.to_dt), "MMM d, yyyy")}
          {report.summary.total_events !== undefined && (
            <span className="ml-2 text-gray-600">
              {report.summary.total_events.toLocaleString()} events
            </span>
          )}
          {(report.summary.ai_agents_involved?.length ?? 0) > 0 && (
            <span className="ml-2 text-indigo-500">
              🤖 {report.summary.ai_agents_involved!.length} AI agent
              {report.summary.ai_agents_involved!.length > 1 ? "s" : ""}
            </span>
          )}
        </p>
      </div>
      {report.status === "ready" && (
        <a
          href={`/api/internal/proxy/compliance/reports/${report.id}/download`}
          download
          className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 hover:border-gray-500 hover:text-white"
        >
          Download
        </a>
      )}
    </div>
  );
}
