import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sentinel — Security & Audit Intelligence Platform",
};

// Static page — no dynamic data in Phase 1
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col">
      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <SentinelLogo />
            <span className="text-lg font-semibold tracking-tight text-white">
              Sentinel
            </span>
          </div>
          <div className="flex items-center gap-6">
            <a
              href="/api/schema/redoc/"
              className="text-sm text-gray-400 transition-colors hover:text-white"
            >
              API Docs
            </a>
            <a
              href="https://github.com/your-org/sentinel"
              className="text-sm text-gray-400 transition-colors hover:text-white"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            <a
              href="/dashboard"
              className="rounded-md bg-sentinel-600 px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-sentinel-500"
            >
              Dashboard
            </a>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex flex-1 flex-col items-center justify-center px-6 py-32 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-sentinel-800/60 bg-sentinel-950/50 px-4 py-1.5 text-xs text-sentinel-300">
          <span className="h-1.5 w-1.5 rounded-full bg-sentinel-400" />
          Phase 1 Foundation — Active Development
        </div>

        <h1 className="max-w-3xl text-5xl font-bold leading-tight tracking-tight text-white md:text-6xl">
          Security Infrastructure for{" "}
          <span className="bg-gradient-to-r from-sentinel-400 to-indigo-400 bg-clip-text text-transparent">
            Financial Systems
          </span>
        </h1>

        <p className="mt-6 max-w-xl text-lg leading-relaxed text-gray-400">
          Immutable audit trails, real-time risk intelligence, and complete
          observability for every action in your fintech stack.
        </p>

        <div className="mt-10 flex items-center gap-4">
          <a
            href="/api/v1/"
            className="rounded-md bg-sentinel-600 px-6 py-2.5 text-sm font-semibold text-white shadow transition-colors hover:bg-sentinel-500"
          >
            Explore the API
          </a>
          <a
            href="https://github.com/your-org/sentinel"
            className="rounded-md border border-gray-700 px-6 py-2.5 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-500 hover:text-white"
            target="_blank"
            rel="noopener noreferrer"
          >
            View on GitHub
          </a>
        </div>
      </section>

      {/* Capability Cards */}
      <section className="border-t border-gray-800 bg-gray-900/50 px-6 py-24">
        <div className="mx-auto max-w-7xl">
          <h2 className="mb-12 text-center text-2xl font-semibold text-white">
            Platform Capabilities
          </h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {CAPABILITIES.map((cap) => (
              <CapabilityCard key={cap.title} {...cap} />
            ))}
          </div>
        </div>
      </section>

      {/* System Status Strip */}
      <SystemStatusStrip />

      {/* Footer */}
      <footer className="border-t border-gray-800 px-6 py-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between text-sm text-gray-500">
          <span>Sentinel — Open Source Security Infrastructure</span>
          <div className="flex gap-6">
            <a href="/api/schema/redoc/" className="hover:text-gray-300">
              API Reference
            </a>
            <a href="/health/" className="hover:text-gray-300">
              System Health
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}

// =============================================================================
// Sub-components
// =============================================================================

function SentinelLogo() {
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sentinel-600">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className="h-5 w-5 text-white"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
        />
      </svg>
    </div>
  );
}

interface CapabilityCardProps {
  title: string;
  description: string;
  phase: string;
  status: "active" | "upcoming";
  icon: string;
}

function CapabilityCard({
  title,
  description,
  phase,
  status,
  icon,
}: CapabilityCardProps) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 transition-colors hover:border-gray-700">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            status === "active"
              ? "bg-green-900/50 text-green-400"
              : "bg-gray-800 text-gray-500"
          }`}
        >
          {phase}
        </span>
      </div>
      <h3 className="mb-2 font-semibold text-white">{title}</h3>
      <p className="text-sm leading-relaxed text-gray-400">{description}</p>
    </div>
  );
}

async function SystemStatusStrip() {
  // Server component — fetch status directly (no client-side fetch)
  let apiStatus: "operational" | "degraded" | "unknown" = "unknown";

  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://backend:8000"}/health/live/`,
      { next: { revalidate: 30 }, signal: AbortSignal.timeout(3000) }
    );
    if (res.ok) apiStatus = "operational";
    else apiStatus = "degraded";
  } catch {
    apiStatus = "unknown";
  }

  const statusConfig = {
    operational: { dot: "bg-green-400", text: "text-green-400", label: "All systems operational" },
    degraded: { dot: "bg-yellow-400", text: "text-yellow-400", label: "Partial degradation detected" },
    unknown: { dot: "bg-gray-500", text: "text-gray-400", label: "Status unavailable" },
  }[apiStatus];

  return (
    <div className="border-t border-gray-800 bg-gray-950 px-6 py-4">
      <div className="mx-auto flex max-w-7xl items-center justify-center gap-2 text-sm">
        <span className={`h-2 w-2 rounded-full ${statusConfig.dot}`} />
        <span className={statusConfig.text}>{statusConfig.label}</span>
        <span className="text-gray-600">·</span>
        <a href="/health/" className="text-gray-500 hover:text-gray-300">
          View status →
        </a>
      </div>
    </div>
  );
}

// =============================================================================
// Data
// =============================================================================

const CAPABILITIES: CapabilityCardProps[] = [
  {
    title: "Immutable Audit Ledger",
    description:
      "Every security-relevant action is recorded as an immutable, signed event. Cryptographic proof of what happened and when.",
    phase: "Phase 2",
    status: "upcoming",
    icon: "📋",
  },
  {
    title: "Risk Intelligence Engine",
    description:
      "Real-time behavioral analysis detects impossible travel, velocity spikes, and anomalous patterns before damage occurs.",
    phase: "Phase 3",
    status: "upcoming",
    icon: "🧠",
  },
  {
    title: "Event Streaming",
    description:
      "Kafka-backed event pipeline processes millions of events per day with ordered, durable, replayable delivery.",
    phase: "Phase 2",
    status: "upcoming",
    icon: "⚡",
  },
  {
    title: "API Key Management",
    description:
      "Scoped API keys with HMAC-SHA256 hashed storage, rotation support, usage tracking, and expiry enforcement.",
    phase: "Phase 3",
    status: "upcoming",
    icon: "🔑",
  },
  {
    title: "Observability Stack",
    description:
      "OpenTelemetry traces, Prometheus metrics, and structured JSON logging on every request — from day one.",
    phase: "Phase 1",
    status: "active",
    icon: "📊",
  },
  {
    title: "Compliance Reports",
    description:
      "Export audit evidence for PCI-DSS, SOC 2, and custom compliance requirements with date-range filtering.",
    phase: "Phase 4",
    status: "upcoming",
    icon: "📑",
  },
];
