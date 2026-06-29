# The Missing Trust Layer in AI-Powered Financial Systems

Something changed in the last two years that most fintech security teams haven't fully reckoned with yet.

Financial systems no longer have only human users.

They have humans, backend services, mobile clients, third-party APIs — and now **AI agents**. Support bots answering customer queries with access to account data. AI models reviewing transactions and flagging fraud. Code assistants that write and sometimes deploy code with access to production secrets. MCP servers connecting AI tools directly to internal APIs. Automated pipelines where AI makes decisions nobody manually approved.

All of these actors are interacting with the same infrastructure. All of them have access to sensitive data. And almost none of them are being audited with the same rigor we apply to human actions.

That is the security problem of the AI era. And it's sitting largely unaddressed inside most fintech companies right now.

---

## What the Attack Surface Looks Like Today

Consider what a mid-sized fintech company might have in production right now:

- A customer support AI agent with read access to account data and transaction history
- An AI fraud detection model that can flag, hold, or approve transactions
- An AI-assisted code review tool with access to the codebase and sometimes secrets
- MCP servers connecting internal APIs to AI tools used by engineers and ops teams
- AI-generated summaries of customer complaints that include PII
- Automated reconciliation pipelines where AI makes decisions on discrepancies

Each of these represents a non-human actor with elevated access to sensitive systems.

Now ask the questions that matter:

- If the support AI suddenly exports 50,000 customer records because of a badly crafted prompt, will you know before the export completes?
- If the fraud AI starts approving anomalous transactions because its behavior drifted, how long before you catch it?
- If an MCP server is compromised and begins making unauthorized API calls, can you reconstruct every action it took?
- If a regulator asks you to prove what your AI systems did with customer data last quarter, do you have that record?

For most companies, the honest answer to all four is: **not confidently**.

---

## The Original Problem Hasn't Gone Away Either

Before AI agents even entered the picture, financial systems had a foundational audit problem that most teams deferred until it was urgent.

The missing trail. An admin performs a bulk action — approves transfers, resets accounts, modifies limits. No record of who did it, from where, or when. An incident investigation starts from zero.

The unverifiable record. A disputed transaction log shows it was approved. The customer insists it wasn't. The log could have been modified by a database admin. There's no cryptographic proof it hasn't been.

The invisible blast radius. A compromised credential was active for six days. Nobody knows which resources it touched because nothing was systematically recorded.

The slow investigation. Something goes wrong. Engineering spends three days parsing raw database logs across six services, correlating request IDs manually. A purpose-built tool would take minutes.

These problems existed before AI. AI makes them harder, faster-moving, and higher-stakes.

---

## Why AI Makes the Audit Problem Worse

Human behavior has patterns. An analyst who logs in at 9am from Lagos and accesses 200 customer records is unusual if they normally access 20. You can build a baseline. You can detect deviation.

AI agents operate at a different scale and speed. An AI agent can make 10,000 API calls in the time it takes a human to review one. It can access data across the entire customer base in minutes. It doesn't follow business hours. It doesn't have a "normal" pattern the way a human does.

This means:

**Volume thresholds matter more.** An AI agent accessing 50,000 records isn't inherently suspicious — it might be running a legitimate report. But it's also the signature of a data exfiltration. The difference is context, timing, and whether the access pattern matches what was authorized.

**Attribution is harder.** When a human does something wrong, there's a name attached. When an AI agent does something wrong, who is responsible? The engineer who deployed it? The product manager who approved the feature? The model provider? Without clear actor identity on every AI action, accountability dissolves.

**Incidents move faster.** A human attacker who gains access to a privileged account might spend days carefully exfiltrating data to avoid detection. An AI agent with a bad prompt or a compromised connection can cause damage in seconds. Detection and response need to be near-real-time.

**The audit trail needs to know what kind of actor acted.** A compliance report that says "customer data was accessed" is incomplete if it doesn't distinguish between a human analyst, a backend service, and an AI agent. These are different risk profiles with different authorization models.

---

## What Trust Actually Requires

The question "can we trust what our AI systems are doing?" has a technical answer. Trust is not a feeling — it's a set of verifiable properties:

**Attribution.** Every action — by every actor, human or AI — is recorded with identity. The record says who acted, what they acted on, when, from where, and in what context. AI agents have named identities, not anonymous service accounts.

**Immutability.** The audit record cannot be modified after the fact. Not by a DBA. Not by an engineer with production access. The record is cryptographically signed at creation. Tampering is detectable.

**Real-time visibility.** Anomalous behavior is detected as it happens, not during the monthly audit. An AI agent that starts behaving outside its normal pattern triggers an alert within seconds, not weeks.

**Complete reconstructibility.** When something goes wrong, you can reconstruct every action an AI agent took — from first API call to last — with enough context to understand what happened and why.

**Scope enforcement.** AI agents operate within defined permission scopes. Actions outside that scope are blocked or immediately flagged. The audit trail shows the boundary was enforced.

These are engineering properties. They can be built. But they need to be built deliberately, before the incident — not retrofitted afterward.

---

## What We're Building

Sentinel is an open-source security infrastructure platform designed for exactly this environment.

It's not an AI product. It doesn't use AI to do security. It's infrastructure for companies that are *adopting* AI — the trust layer between AI agents, human users, and the financial systems they interact with.

The core idea: treat every action by every actor — human or AI — as a first-class auditable event. Record it immutably. Score it for risk in real time. Alert when something anomalous happens. Make every incident reconstructible in minutes, not days.

We're building it in public, phase by phase, with every architectural decision documented and the full codebase open source.

The next post covers what we've built so far: the foundation and the audit ledger — and why every technical decision we made is designed to handle both human users and AI agents equally.

---

*Sentinel is open source. GitHub: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*
