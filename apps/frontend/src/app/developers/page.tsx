import Link from "next/link";
import { ArrowUpRight, KeyRound, Fingerprint } from "lucide-react";
import { PublicNav } from "@/components/brand";
export const metadata = { title: "Developer guide" };
export default function Developers() {
  return (
    <>
      <PublicNav />
      <main className="guide-page">
        <div className="eyebrow">DEVELOPER EXPERIENCE</div>
        <h1>
          A few endpoints.
          <br />A complete perspective.
        </h1>
        <p className="guide-intro">
          Connect your application to Sentinel 2. Attribute actions with scoped
          credentials, record signed events and follow the resulting risk
          signals.
        </p>
        <div className="hero-actions">
          <Link className="button button-dark" href="/api-keys">
            Manage API keys <KeyRound size={16} />
          </Link>
          <a
            className="button button-white"
            href="/api/schema"
            target="_blank"
            rel="noopener noreferrer"
          >
            OpenAPI schema <ArrowUpRight size={16} />
          </a>
        </div>
        <div className="guide-grid">
          <section className="guide-card">
            <Fingerprint size={25} className="mb-5 text-slate-400" />
            <h2>01. Establish identity.</h2>
            <p>
              Create a key in <Link href="/api-keys">API keys</Link>. Choose a
              service or AI agent and give it only the scopes it needs. Use the{" "}
              <code>X-API-Key</code> header when ingesting events. Actor
              identity comes from the credential, rather than an untrusted
              request body.
            </p>
          </section>
          <section className="guide-card">
            <KeyRound size={25} className="mb-5 text-slate-400" />
            <h2>02. Follow the evidence.</h2>
            <p>
              Events move through the transactional outbox and Kafka before risk
              scoring. Open the <Link href="/events">audit log</Link> to inspect
              an event, then follow its actor timeline or investigate the
              corresponding <Link href="/alerts">alerts</Link>. A pending score
              means processing has not finished yet.
            </p>
          </section>
        </div>
        <section className="guide-card">
          <h2>Your API map.</h2>
          <p>
            Backend paths are shown below. Browser requests use Sentinel’s
            authenticated internal proxy; server integrations should use your
            configured backend origin. The OpenAPI schema includes request
            fields, response shapes and authentication requirements.
          </p>
          <div className="endpoint-list">
            {[
              ["POST", "/api/v1/auth/login/"],
              ["GET", "/api/v1/events/"],
              ["POST", "/api/v1/events/ingest/"],
              ["GET", "/api/v1/risk/summary/"],
              ["GET", "/api/v1/alerts/"],
              ["GET", "/api/v1/api-keys/"],
              ["POST", "/api/v1/api-keys/create/"],
              ["GET / POST", "/api/v1/compliance/reports/"],
            ].map(([m, p]) => (
              <div className="endpoint" key={p}>
                <strong>{m}</strong>
                <code>{p}</code>
              </div>
            ))}
          </div>
        </section>
        <div className="hero-actions">
          <a
            className="button button-quiet"
            href="https://github.com/Gwerdonatus/Sentinel/tree/fix/reliable-audit-pipeline/sdk"
            target="_blank"
            rel="noopener noreferrer"
          >
            Explore the Python SDK <ArrowUpRight size={16} />
          </a>
          <Link className="button button-quiet" href="/dashboard">
            Return to workspace <ArrowUpRight size={16} />
          </Link>
        </div>
      </main>
    </>
  );
}
