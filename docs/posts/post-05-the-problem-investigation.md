# The Investigation Problem: Why Security Events Mean Nothing Without Context

*This is the fifth post in the Sentinel series. Previous: [Building Sentinel: Risk Intelligence & AI Actor Tracking](#).*

Phases 1 through 3 built a system that can record every action, score every event for risk, and fire an alert within seconds of something anomalous happening.

Phase 4 is about what happens next.

An alert fires. A security analyst gets a Slack message at 11:47pm: "High Risk AI Agent Action — support-bot-v2, score 73, resource_type: transaction_history." They open their laptop. Now what?

This is the investigation problem. It's less glamorous than the risk scoring algorithm, and it gets less attention in security tooling conversations. But it's the thing that determines whether your security infrastructure is actually useful or just a source of noise that eventually gets muted.

---

## What a Useful Investigation Actually Requires

When that alert fires, the analyst needs to answer a sequence of questions, each of which depends on the answer to the previous one:

**What exactly happened?** Not "a risk signal fired." The specific event: which action, on which resource, at what time, with what context in the metadata.

**Is this actually unusual for this actor?** A support bot that routinely accesses transaction data as part of a legitimate daily report would have a baseline that makes a 10x volume spike meaningful. The same 10x spike from a bot that never normally touches transaction data is a different severity entirely. You cannot answer this question without seeing the actor's history.

**How long has this been happening?** A single anomalous event is different from a pattern that started three days ago and has been escalating. The investigation needs the full timeline, not the triggering event in isolation.

**What else happened around the same time?** An AI agent accessing unusual data is more concerning if, in the same window, a human user with admin privileges logged in from an unusual location. Correlation across actors requires seeing multiple timelines together.

**What was the resolution last time this actor triggered an alert?** If this same agent triggered a similar alert six weeks ago and it was resolved as a false positive from a legitimate configuration change, that context matters. If it was resolved as a genuine incident, that matters even more.

None of these questions can be answered by looking at a list of events in isolation. They require a view that reconstructs a coherent narrative from raw records.

---

## The Token Storage Problem Nobody Wants to Talk About

Before you can investigate anything, your security team needs to actually log in to the investigation tool. And how authentication tokens are stored in a dashboard directly affects the security of everything that dashboard can access.

This comes up constantly in fintech security tooling and it's usually handled badly.

The common pattern — store the JWT in `localStorage`, read it on every request from client-side JavaScript — is a straightforward XSS attack surface. A single vulnerable dependency or injected script anywhere in the application can read the token directly. For a security investigation tool sitting on top of a full audit ledger and live risk data, that's an unacceptable exposure.

The correct pattern is httpOnly cookies set by a server-side handler, where the token is never accessible to JavaScript at all. The browser sends the cookie automatically on every request. An XSS attack cannot read it. The tradeoff is slightly more architecture: a backend-for-frontend layer that attaches the token server-side before forwarding requests to the actual API.

For a product called Sentinel, building it the insecure way would undermine the entire point.

---

## What Compliance Reports Actually Need to Show

The third problem Phase 4 needed to solve was compliance reporting — and the specific gap that Sentinel can fill that generic audit export tools cannot.

Every organization dealing with financial regulators eventually needs to produce evidence of what happened. PCI-DSS requires evidence of access to cardholder data. SOC 2 requires evidence of access controls, changes to user permissions, and administrative actions. The standard approach is to export the raw audit log in some format and let the auditor figure it out.

The problem with this approach has gotten worse in the AI era. A raw event log that says "customer data was accessed 47,000 times in Q3" leaves the auditor with a legitimate question: was that 47,000 human accesses? 47,000 automated service calls? 47,000 AI agent requests?

The answer matters for the risk assessment. Automated batch processes accessing data in a predictable pattern are different from human users accessing the same data individually. AI agents accessing data in response to natural language queries are different again — their access patterns are harder to predict, their scope of access depends on how the prompts are constructed, and a single compromised prompt can produce access patterns that look nothing like the baseline.

A compliance report that shows this breakdown — human access by named user, service access by service name, AI agent access by agent name and model version — provides substantially more assurance than a raw count. It also makes anomalies visible: if Q3 had 200 accesses from a specific AI agent in July and August and 47,000 in September, that pattern should appear clearly in the evidence package, not be buried in aggregate numbers.

That's the evidence a regulator actually needs to evaluate whether your AI agents are operating within appropriate scope. And it's what Sentinel's compliance reports produce automatically, without requiring the analyst to build a custom query to extract it.

---

## Why the Dashboard Has to Be Fast

One more thing that rarely gets discussed: investigation speed is itself a security property.

When an alert fires about an AI agent behaving anomalously, the cost of the incident depends heavily on how quickly a human can understand what's happening and make a decision. An investigation that takes three hours of log-digging is three hours in which the problem continues.

This means the dashboard can't be a slow database dump wrapped in a web interface. The actor timeline needs to render in under two seconds. The risk score chart needs to show the trend immediately. The alert list needs to sort and filter client-side without a round trip for every interaction.

These are product design constraints that have direct security consequences. A dashboard that security teams stop using because it's slow is a dashboard that doesn't prevent incidents.

---

## What Phase 4 Builds

Phase 4 is the operational surface: the interface a security team actually uses, built around investigation as the primary user journey.

The anchor view is the actor timeline — any actor (human or AI agent), their complete event history with risk scores plotted over time, their open alerts, and the full detail of any individual event. This is the view that answers "what exactly did this AI agent do between 11pm and midnight."

Built on top of that is the alert inbox — the starting point for any investigation, with filters for severity, status, and actor type that let a team triage at a glance. The compliance report generator that produces AI-attribution-forward evidence packages in PDF, CSV, or JSON format. The AI agents view that shows every registered agent, its behavioral history, and a direct link to its timeline.

And the authentication is built correctly: httpOnly cookies, BFF proxy, automatic silent token refresh. The investigation tool doesn't introduce the vulnerabilities it's supposed to help detect.

Next post: the technical implementation — the BFF authentication pattern in Next.js App Router, how TanStack Query manages the investigation UI state, and what goes into a compliance PDF that an auditor can actually use.

---

*Sentinel is open source: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*
