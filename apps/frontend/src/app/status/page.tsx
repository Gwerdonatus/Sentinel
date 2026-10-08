import Link from "next/link";
import { PublicNav } from "@/components/brand";
export const dynamic = "force-dynamic";
export const metadata = { title: "System status" };
export default async function Status() {
  let backend = false;
  try {
    const r = await fetch(
      `${process.env.BACKEND_INTERNAL_URL ?? "http://backend:8000"}/health/live/`,
      { cache: "no-store", signal: AbortSignal.timeout(3000) },
    );
    backend = r.ok;
  } catch {
    backend = false;
  }
  return (
    <>
      <PublicNav />
      <main className="guide-page">
        <div className="eyebrow">SYSTEM STATUS</div>
        <h1>
          {backend ? "Connected.\nReady to observe." : "A signal is missing."}
        </h1>
        <p className="guide-intro">
          Current availability from the Sentinel 2 web application. These checks
          cover the web frontend and backend liveness; they do not certify every
          background service.
        </p>
        <section className="guide-card">
          <div className="status-item">
            <span>
              <span className="status-dot" />
              Web application
            </span>
            <strong>Operational</strong>
          </div>
          <div className="status-item">
            <span>Backend API</span>
            <strong>{backend ? "Reachable" : "Unavailable"}</strong>
          </div>
          <div className="status-item">
            <span>Checked at</span>
            <time>
              {new Date().toISOString().replace("T", " ").slice(0, 19)} UTC
            </time>
          </div>
          <p className="mt-5">
            Refresh this page for a new check. Workspace data is available after
            sign-in.
          </p>
        </section>
        <div className="hero-actions">
          <Link href="/dashboard" className="button button-dark">
            Open workspace ↗
          </Link>
          <a href="/status" className="button button-white">
            Check again
          </a>
        </div>
      </main>
    </>
  );
}
