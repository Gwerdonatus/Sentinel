import Link from "next/link";
import {
  ArrowUpRight,
  Fingerprint,
  ScanEye,
  Workflow,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { PublicNav, SentinelMark, Brand } from "@/components/brand";

export default function HomePage() {
  return (
    <main className="landing">
      <PublicNav />
      <section className="hero">
        <div className="hero-copy">
          <div className="eyebrow">
            <span className="status-dot" /> ALWAYS WATCHFUL. ALWAYS ACCOUNTABLE.
          </div>
          <h1>
            Every action.
            <br />
            In your sight.
          </h1>
          <p>
            The watchman for your financial systems. Bring human, service and AI
            activity into one clear view — with a signed record of every action.
          </p>
          <div className="hero-actions">
            <Link href="/dashboard" className="button button-dark">
              Enter your workspace <ArrowUpRight size={17} />
            </Link>
            <Link href="/developers" className="button button-quiet">
              Explore the API <ArrowRight size={16} />
            </Link>
          </div>
          <div className="hero-note">
            <ShieldCheck size={15} /> Signed events. Attributed actors.
            Explainable risk.
          </div>
        </div>
        <div
          className="watch-visual"
          role="img"
          aria-label="Sentinel watchman observing human, service and AI activity"
        >
          <div className="orbital orbit-one" />
          <div className="orbital orbit-two" />
          <div className="orbital orbit-three" />
          <div className="visual-crosshair" />
          <div className="watch-core">
            <SentinelMark />
          </div>
          <div className="signal signal-agent">
            <ScanEye size={18} />
            <div>
              <strong>AI agent</strong>
              <span>Activity in focus</span>
            </div>
            <span className="signal-light" />
          </div>
          <div className="signal signal-event">
            <Fingerprint size={18} />
            <div>
              <strong>Audit event</strong>
              <span>Signed at the source</span>
            </div>
            <span className="signal-light" />
          </div>
          <div className="visual-caption">
            <span className="status-dot" /> A CLEARER SIGNAL. A CALMER RESPONSE.
          </div>
        </div>
      </section>
      <section className="principle-strip">
        <span>Built for a world that never stops.</span>
        <span>
          <Fingerprint size={17} /> Cryptographic provenance
        </span>
        <span>
          <Workflow size={17} /> Durable event delivery
        </span>
        <span>
          <ScanEye size={17} /> AI actor visibility
        </span>
      </section>
      <section id="platform" className="platform-section">
        <div className="section-heading">
          <div className="eyebrow">THE SENTINEL PERSPECTIVE</div>
          <h2>
            Complex systems.
            <br />
            Beautiful clarity.
          </h2>
          <p>
            Less noise between an action and an answer. Follow the evidence from
            the first event to the final investigation.
          </p>
        </div>
        <div className="capability-grid">
          {[
            {
              icon: Fingerprint,
              n: "01",
              title: "A record you can trust.",
              text: "Versioned HMAC signatures preserve event provenance. Trace who acted, what changed and when it happened.",
              href: "/events",
              label: "Explore the audit log",
            },
            {
              icon: ScanEye,
              n: "02",
              title: "See beyond the anomaly.",
              text: "Risk scores with explanations help you understand unusual behavior across people, services and AI agents.",
              href: "/alerts",
              label: "Open risk intelligence",
            },
            {
              icon: Workflow,
              n: "03",
              title: "Every actor. One view.",
              text: "Scoped credentials make agent identity explicit. Connect events, actors and alerts in a single workspace.",
              href: "/ai-agents",
              label: "Discover AI agents",
            },
          ].map(({ icon: Icon, ...c }) => (
            <article className="capability" key={c.n}>
              <div className="capability-top">
                <Icon size={28} strokeWidth={1.4} />
                <span>{c.n}</span>
              </div>
              <h3>{c.title}</h3>
              <p>{c.text}</p>
              <Link href={c.href}>
                {c.label}
                <ArrowUpRight size={16} />
              </Link>
            </article>
          ))}
        </div>
      </section>
      <section className="developer-band">
        <div>
          <div className="eyebrow">MADE TO CONNECT</div>
          <h2>
            Your systems.
            <br />
            Our undivided attention.
          </h2>
          <p>
            Integrate audit events using scoped API keys. Your existing
            infrastructure, with a clearer picture.
          </p>
          <Link href="/developers" className="button button-dark">
            Start building <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="code-window">
          <div className="code-caption">
            <span>EVENT PROVENANCE</span>
            <span>JSON</span>
          </div>
          <pre>
            <code>{`{\n  "event_type": "TRANSFER_INITIATED",\n  "actor_type": "AI_AGENT",\n  "agent_name": "reconciliation-agent",\n  "resource_type": "transfer",\n  "metadata": {\n    "demo_data": true\n  }\n}`}</code>
          </pre>
          <p>Illustrative event · Identity derived from credentials</p>
        </div>
      </section>
      <footer className="public-footer">
        <Brand />
        <span>Watchful by design.</span>
        <Link href="/developers">API guide</Link>
        <a
          href="https://github.com/Gwerdonatus/Sentinel"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub ↗
        </a>
      </footer>
    </main>
  );
}
