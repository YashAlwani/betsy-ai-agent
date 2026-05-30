# Betsy — User Requirements

## Design Philosophy

**Betsy is a layer on top of the procurement environment, not a replacement.**
The underlying procurement system (orders, invoices, suppliers) stays as-is.
Betsy monitors it, flags issues, and makes recommendations — humans stay in control.

---

## Users

**Primary — Operations Manager (Jenny)**
- 0 tech background
- Currently spends 30+ hours/week on procurement firefighting
- Needs: quick view of what needs attention, ability to approve/reject agent decisions, confidence that Betsy won't make costly mistakes

**Secondary — Finance Team**
- Needs: audit trail of all autonomous decisions, cost visibility, duplicate invoice alerts

**Tertiary — Production/Assembly**
- Needs: reassurance that materials won't run out, no direct interaction with Betsy

---

## Language Rules (non-negotiable)

- No system jargon anywhere in the UI — no `trigger`, `confidence_score`, `EMA`, `pipeline`
- Betsy speaks in first person: "I ordered...", "I'm not sure about...", "I flagged..."
- Confidence shown as filled dots (●●●●○) not floats (0.87)
- Status labels in plain English: "needs your OK" not `pending_approval`
- Reasons written as short plain sentences: "Stock was running low — 2 days left" not `stockout_risk: days_remaining=2`

---

## Screens

### 1. Home
**Purpose:** Quick health check at a glance. Jenny opens this in the morning.
**Must show:**
- How many items need her approval (with shortcut to screen 2)
- How many things Betsy handled automatically (no action needed)
- How many critical alerts exist
- Last 3–5 activity items in plain English
- When Betsy last checked inventory

**Must NOT show:**
- Technical agent internals
- Raw data tables
- Any number that requires explanation

---

### 2. Pending Approvals (HITL core)
**Purpose:** The place where humans stay in control. Every item here is something Betsy chose NOT to do autonomously.
**Must show per item:**
- What's happening (plain English, 1–2 sentences)
- What Betsy would normally do
- Why she's asking instead of acting (the reason she's unsure)
- What it costs (if a purchase is involved)
- Betsy's confidence level (dots, not float)
- Two clear actions: approve / decline

**UX rules:**
- Each item is a card, not a table row — cards feel more human
- Approve/decline must be impossible to confuse with each other
- After approval: item disappears, brief confirmation shown
- If queue is empty: show a positive "nothing needs your attention" state

---

### 3. Agent Log
**Purpose:** What did Betsy do in the last N days? Full readable history.
**Must show:**
- Grouped by day
- Each entry: what happened, what it cost (if anything), how long ago
- Color coded: auto-handled (green), human-approved (blue), flagged/declined (orange/red)
- Expandable detail per entry with the full plain-English reasoning

**Must NOT show:**
- LangGraph node names
- Raw JSON payloads
- Confidence as a decimal

---

### 4. Supplier Scoreboard
**Purpose:** How are our suppliers performing? Is anyone becoming unreliable?
**Must show:**
- Supplier name, track record (dots), typical delivery speed, last order date
- Visual warning if a supplier has an open issue (e.g. duplicate invoice)
- Note that track record "updates automatically after each delivery" — makes the learning visible without explaining EMA

---

## Functional Requirements

| # | Requirement | Priority |
|---|---|---|
| F1 | Agent decisions persist across server restarts | High |
| F2 | Approval queue shows items until human acts on them | High |
| F3 | Approve action triggers PO creation automatically | High |
| F4 | Decline action logs reason and closes item | High |
| F5 | Agent runs on a schedule without manual trigger | High |
| F6 | Supplier track record updates after each delivery | Medium |
| F7 | Expandable reasoning per log entry | Medium |
| F8 | Finance can export/audit all decisions | Low |

---

## Non-Functional Requirements

| # | Requirement |
|---|---|
| N1 | Zero setup for end user — open browser, it works |
| N2 | Any decision Betsy makes autonomously must be logged with a plain-English reason |
| N3 | No autonomous action above €5,000 — always requires human |
| N4 | If Betsy is offline or erroring, the procurement environment continues normally |
| N5 | Every approval/rejection is timestamped and attributed |

---

## What This Is NOT

- Not a replacement for the ERP or procurement system
- Not a tool for suppliers to interact with
- Not a reporting/analytics platform (that's a future version)
- Not something IT needs to babysit

---

*Referenced by: DL-03 (tech stack decisions), dashboard/wireframe.html (UI design)*
