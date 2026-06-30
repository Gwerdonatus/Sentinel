# How Do You Audit What an AI Agent Does?

*This is the third post in the Sentinel series. Previous posts: [The Missing Trust Layer in AI-Powered Financial Systems](#) and [Building Sentinel: Foundation + Audit Ledger for the AI Era](#).*

Phase 2 gave Sentinel an immutable audit ledger — every action recorded, signed, tamper-evident. That solved the first half of the problem: proving what happened.

It didn't solve the second half: **knowing whether what happened should worry you.**

A human analyst accessing 200 customer records at 3am is a signal. An AI agent accessing 200 customer records is — what, exactly? AI agents routinely process large volumes of data as part of their normal function. The same action that would be alarming from a human can be completely unremarkable from an AI agent, and vice versa. A single API call that does something subtly outside its intended scope can be invisible in an event-by-event view but glaringly obvious against a baseline.

This is the question Phase 3 had to answer: **how do you build a security signal out of AI agent behavior, when "normal" for an AI agent looks nothing like "normal" for a human?**

---

## Why Traditional Anomaly Detection Doesn't Transfer

Most fraud and security systems were built around human behavioral baselines. They work because humans have natural rate limits — you can't physically log in from two continents in five minutes, you can't manually process ten thousand records in an hour, you sleep, you take weekends off, your typing has a rhythm.

None of these assumptions hold for AI agents.

**Volume isn't inherently suspicious.** An AI reconciliation agent might legitimately touch every transaction in a daily batch — tens of thousands of records — as part of its normal job. A volume-based alert tuned for humans would fire constantly and be ignored within a week. A volume-based alert tuned correctly for AI needs a *different baseline*: not "is this a lot," but "is this a lot *for this specific agent, compared to its own history*."

**There's no time-of-day signal.** Humans have circadian rhythms baked into their behavior. AI agents run continuously, or on schedules that have nothing to do with business hours. "Off-hours activity" — a classic human security signal — is meaningless for an agent that runs a midnight batch job by design.

**Scope drift is the real threat, not volume.** The actual danger with an AI agent isn't usually that it does *too much* of what it's supposed to do. It's that it starts doing something it was never supposed to do at all — accessing a resource type it's never touched, taking an action outside its configured permissions, behaving in a way that suggests the prompt or configuration driving it has been compromised or has drifted.

**Attribution has to be precise, immediately.** When a human does something wrong, you have a name, a face, an HR record. When "the system" does something wrong, the natural question is: *which* system? Which agent? Which version? Without that answered at the moment of the event — not reconstructed three days later from scattered logs — incident response stalls at step one.

---

## The Real Failure Mode We're Designing Against

Here's the scenario that crystallized the design for Phase 3:

A company runs an AI support agent with read access to customer account data, scoped specifically to answer billing questions. One day, due to a prompt injection in a customer message, or a misconfigured tool integration, or simply model drift after an update, the agent starts pulling full transaction histories instead of billing summaries — and doing it for accounts well outside the conversation it's supposed to be handling.

Every individual API call the agent makes is, on its own, completely valid. It has a real API key. It's hitting an endpoint it's authorized to use. Nothing about any single request looks like an attack.

What makes this an incident is the *pattern*: this agent has never touched the `transaction_history` resource type before. This agent's request volume just jumped 15x in the last hour. This agent is now accessing accounts that have no relationship to its current conversation context.

None of these signals exist if you're only looking at individual events. All three exist clearly if you're comparing behavior against the agent's own established baseline.

That's the problem Phase 3 had to solve: **build a system that can say, with precision, "this specific named agent is acting differently than it usually does" — and do it within seconds, not after a quarterly review.**

---

## What "Trust" Means for an AI Agent, Specifically

If we're going to call something a "trust layer," it needs to do more than log. It needs to make a judgment, continuously, about whether to trust what's happening right now.

For AI agents specifically, that judgment requires answering:

**Is this agent who it claims to be?** Not "did a valid credential get presented" — any compromised key passes that check. The deeper question is whether the *behavior* matches the identity. A support bot suddenly behaving like a data export tool is a credential that's technically valid and a behavior that's a red flag.

**Is this within the agent's established pattern?** Every agent should have a behavioral fingerprint — what resource types it touches, what volume it operates at, what times it's active. Deviation from that fingerprint is the signal, regardless of whether the deviation looks "big" in absolute terms.

**Does this look like scope creep or compromise?** The first time an agent touches a new resource type isn't automatically bad — agents get new capabilities deployed. But it's exactly the kind of event that should be visible and reviewable, not silently absorbed into the noise.

**Can we act on this in real time, not in a postmortem?** A risk signal that surfaces during a monthly audit is forensics. A risk signal that surfaces within seconds and pages someone is prevention. For AI agents — which can cause damage at machine speed — the gap between detection and action has to be measured in seconds.

---

## What We're Building to Answer This

Phase 3 of Sentinel is the risk intelligence engine: a system that scores every audit event in real time, with separate behavioral models for human actors and AI agents, and fires alerts the moment a score crosses a meaningful threshold.

It treats AI agents as first-class, named entities — not anonymous service accounts — so that "which agent did this" is answered instantly, not reconstructed from logs.

It builds baselines per agent, not global thresholds, so that a reconciliation bot's normal high-volume behavior and a support bot's normal low-volume behavior are each judged against their own history, not against each other.

It looks specifically for the signal that matters most for AI agents: not "how much," but "different than before" — new resource types, volume spikes relative to *that agent's own pattern*, and the kind of subtle scope drift that an attacker or a malfunctioning prompt would produce.

And it does all of this on the same immutable, signed audit ledger from Phase 2 — so every alert traces back to a tamper-evident record of exactly what happened.

The next post covers how we actually built it: the scoring algorithm, why we rejected a rule DSL with `eval()` in favor of structured JSON conditions, and the one deliberate exception we made to the immutability guarantee from Phase 2 — and why making that exception explicit matters more than pretending it doesn't exist.

---

*Sentinel is open source. GitHub: [github.com/Gwerdonatus/Sentinel](https://github.com/Gwerdonatus/Sentinel)*
