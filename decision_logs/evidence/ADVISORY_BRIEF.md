# Betsy — Advisory Brief

Stakeholder-facing recommendations extracted from the project decision logs.
Each section corresponds to one DL and is written for a non-technical audience
(operations manager, PM, or finance lead), not for a developer.

---

## DL-01 — Start with visibility, not automation

Before deploying any autonomous procurement system, the first deliverable
should be a dashboard that shows what "normal" and "critical" actually look like
in your own data. You cannot trust an autonomous system to act on problems you
cannot yet see yourself.

The 4-scenario test suite (stockout, price spike, duplicate invoice, supplier
out-of-stock) should be a non-negotiable acceptance criterion for any vendor
selling procurement AI. If they cannot demonstrate clear, reproducible agent
behavior across all four failure modes against sample data — do not sign.

---

## DL-02 — Start simple, escalate to parallel only when you need it

For a PM or client rolling out procurement automation: begin with the
sequential Pipeline architecture. Every decision is traceable to a specific
step, and when something goes wrong you can pinpoint exactly where.

Only move to a parallel multi-agent architecture (Orchestra) once the
sequential system is confirmed working and you are hitting scenarios where two
independent problems occur simultaneously — a stockout and a duplicate invoice
from the same supplier, for example.

The autonomous spending limit (MAX_AUTO_USD) is not a technical setting. It is
a business policy that belongs to finance. Agree on that number with the finance
team before writing the first agent node — not after the first unexpected
$50,000 PO.

---

## DL-03 — Lead with the reasoning, not the action

For any AI tool aimed at non-technical users, the design rule is: explain
before you ask. Do not present an Approve / Decline button without first stating
what happened, what the agent would normally do, and why it stopped and asked.
An approval card that skips the explanation produces approvals the user does not
understand — which is worse than no automation at all.

Show confidence as a visual indicator (three dots, a bar) rather than a decimal
like 0.87. Low confidence is exactly the signal that a human should be
involved — make sure the user can see that is why they are being asked.

---

## DL-04 — The financial safeguard is the demonstration, not a failure

Do not raise the autonomous spending limit to make a demo look more impressive.
A procurement agent that escalates a $12,000 order for human review is more
trustworthy than one that approves it silently. The escalation is the safety
story.

For a stakeholder demo, the correct scenario to show autonomous action is a
small, cheap restock: one that sits comfortably under the spending limit so the
agent places the order, the PO appears in the environment in real time, and the
audience can see the full autonomous loop close. Reserve the high-value
escalation scenario for the trust and safeguards conversation.

---

## DL-05 — Store the decision payload at queue time, not a reference to replay it

When building a human-in-the-loop approval system, store the full purchase
order payload the moment the agent makes its decision — supplier, SKU, quantity,
unit price, and reasoning. Execute that stored payload when the human approves.

Do not defer execution and recompute when the human responds. Recomputing
introduces a second model call, the risk that prices or stock levels have
changed since the original decision, and unnecessary complexity. The pattern
— decide early, store payload, execute on approval — is how well-designed
approval systems work for exactly this reason.

---

## DL-06 — Persistence is the trust layer, not a nice-to-have

For any AI system that needs to be trusted by a non-technical user, persisting
decisions across server restarts is not optional. A user cannot act on a pending
$11,000 purchase order if she is not sure it will still be there after the
weekend.

A write-through SQLite pattern — append on every action, reload on boot — is
the right first persistence layer at this project scale. The application code
does not change when the database is later swapped to PostgreSQL for a
production deployment; only the connection layer changes.

---

## DL-07 — Score learning must be tested at the decision level, not just the formula level

Verifying that a learning formula produces the correct numbers is a necessary
condition for intelligent behavior — but it is not sufficient. A score that
updates correctly but never changes what gets ordered is accounting, not
learning.

The acceptance test for supplier scoring is: given two agents where one has
accumulated a poor delivery record and one has accumulated a good record, does
the agent order from a different supplier the second time? If the answer is yes
and the score trajectory is mathematically predictable at each step, the
learning claim is defensible to a stakeholder or auditor.

Note: an LLM-based evaluate node may weight lead time heavily for a critical
stockout even when a supplier's reliability score has fallen. That is not
necessarily wrong — it may be the right procurement call under urgency. If the
model's recommendation diverges from the composite score ranking, that
divergence is itself evidence worth capturing and presenting.

---

## DL-08 — Notifications must reach the user outside the dashboard

A notification that only appears inside the browser dashboard is not a
notification — it is a badge the user has to remember to look for. For an
operations manager who is not sitting in front of betsy.html, pending decisions
sit unseen in the approval queue.

For a system at this scale, desktop toast notifications and email (via standard
SMTP) cover the two channels an operations manager actually monitors: the active
screen and the inbox. This requires no external service accounts, no third-party
dependencies, and no integration with a specific communications platform — which
matters for educational portability and for deployments where Slack or Teams
access is restricted.

Notification failure must never interrupt the agent execution path. Every send
call should be wrapped so that a misconfigured SMTP server or an unavailable
desktop notification library produces a silent log entry, not a crashed pipeline.
