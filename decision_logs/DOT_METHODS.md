# Betsy — DOT Framework Method Usage

Maps every DOT research strategy used across the project to the DL it appears
in and the evidence files that support it.

---

## Summary table

| DL | Library | Showroom | Lab | Field | Workshop |
|----|---------|----------|-----|-------|----------|
| DL-01 | | | ✅ | | ✅ |
| DL-02 | ✅ | ✅ | ✅ | | |
| DL-03 | ✅ | ✅ | | | |
| DL-04 | | | ✅ | ✅ | |
| DL-05 | | | ✅ | | |
| DL-06 | | | ✅ | | |
| DL-07 | | | ✅ | | |
| DL-08 | | | ✅ | | |

---

## By strategy

### Library
*Desk research into existing tools, frameworks, or literature.*

**DL-02 — Agent framework selection**
Compared LangGraph, AutoGen, CrewAI, and n8n against Betsy's procurement
requirements before choosing LangGraph.
Evidence: `PIPELINE_ARCHITECTURE.md` · `ORCHESTRA_ARCHITECTURE.md`

**DL-03 — UI pattern research**
Studied how Salesforce Einstein, Microsoft Copilot, Tableau Pulse, Glean, and
Notion AI present AI to non-technical business users. Extracted four recurring
patterns (command bar, narrative, AI-scored tables, inline approval cards).
Evidence: `docs/user_requirements.md` · `docs/wireframes.md`

---

### Showroom
*Building or demonstrating prototypes to compare approaches or validate a direction.*

**DL-02 — Pipeline vs Orchestra comparison**
Both architectures built and run against the same 4 scenarios. Outputs
compared directly to identify the failure case (sequential processing of
simultaneous stockout + duplicate invoice).
Evidence: `graph.py` · `decide.py` · `inventory_monitor.py` ·
`supplier_scout.py` · `invoice_auditor.py` · `PIPELINE_ARCHITECTURE.md` ·
`ORCHESTRA_ARCHITECTURE.md`

**DL-03 — Interactive wireframe prototype**
`dashboard/wireframe.html` built as a fully interactive HTML prototype with
working navigation, approve/decline buttons, expandable log entries, and a
live badge counter — used to validate layout and interaction model before
touching the real dashboard.
Evidence: `dashboard/wireframe.html` · `images/dl03-wireframe-comparison.png` ·
`images/dl03-wireframe-interactive.png`

---

### Lab
*Controlled technical experiments: building, testing, and validating in isolation.*

**DL-01 — Mock environment construction and scenario validation**
Built 12 SKUs, 6 suppliers, 15 invoices, 4 injectable scenarios, FastAPI
server, and live dashboard. Validated all 4 scenarios produce reproducible,
resettable, non-bleeding results.
Evidence: `inventory.json` · `suppliers.json` · `stockout_warning.json` ·
`duplicate_invoice.json` · `state.py`

**DL-02 — Architecture conflict resolution test**
Combined stockout + duplicate invoice scenario run against both Pipeline and
Orchestra to confirm the sequential pattern fails and Orchestra's precedence
table resolves it correctly.
Evidence: `graph.py` · `decide.py` · `llm.py` · `api_client.py`

**DL-04 — Live integration and model selection**
Wired betsy.html to the live FastAPI endpoints, added POST /api/run-agent,
switched from Mistral 7B to Llama 3.1 8B, ran stockout_warning end-to-end.
Evidence: `dashboard/betsy.html` · `server/main.py` · `shared/llm.py` ·
`pipeline/nodes/decide.py`

**DL-05 — HITL approval queue: 11 test cases**
Built /api/approvals and ran 11 test cases covering: empty queue, populate on
run, approve, reject, double-resolve guard (400), unknown ID guard (404).
Found and fixed the state.reset() bug that cleared approvals between runs.
Evidence: `server/routers/approvals.py` · `pipeline/nodes/act.py` ·
`shared/api_client.py` · `server/state.py` · `docs/test-report-dl05.md`

**DL-06 — Persistence restart test and EMA formula verification**
Restart test: 7 log entries and 1 pending approval reloaded from betsy.db
after hard server kill — zero entries lost. EMA formula verified to four
decimal places against two known inputs.
Evidence: `server/db.py` · `server/scheduler_instance.py` ·
`server/routers/stats.py` · `server/routers/orders.py` ·
`tests/test_ema_learning.py` · `docs/test-report-dl06.md`

**DL-07 — Long-term learning integration test**
Two real LLM pipeline runs with 8 structured delivery rounds between them.
QuickShip 0.92 → 0.44 (5 × 8-day-late), FastParts 0.95 → 0.97 (3 × on-time).
Composite crossover confirmed at round 5 with exact predicted values.
Evidence: `tests/test_long_term_learning.py` · `server/routers/suppliers.py` ·
`pipeline/nodes/evaluate.py`

**DL-08 — Notification system: 22 unit tests**
Desktop (plyer) and email (smtplib) channels tested with mocked sends. All
toggle, truncation, exception-swallowing, and config coercion cases covered.
22/22 passing in 0.27s.
Evidence: `server/notifier.py` · `server/config.py` ·
`server/routers/notifications.py` · `tests/test_notifier.py`

---

### Field
*Testing in a realistic or real-world context — observing actual behaviour
rather than a controlled scenario.*

**DL-04 — First real end-to-end agent run**
Ran the stockout_warning scenario against the live environment for the first
time. Observed the financial safeguard trigger ($11,937 PO > $5,000 limit →
pending_human_review). Confirmed the safeguard is working as designed, not
a failure.
Evidence: `images/dl04-pipeline-first-run.png` · `images/dl04-betsy-live-data.png` ·
`images/dl04-run-betsy-controls.png`

---

### Workshop
*Hands-on design sessions: schema design, tradeoff structuring, environment modelling.*

**DL-01 — Procurement data schema design**
Designed the SKU and supplier data schemas from scratch — determining which
fields (reorder_point, daily_usage_avg, lead_days, unit_price) are required
for agent decision-making vs. nice-to-have. Designed real supplier tradeoffs
(fast + expensive vs. cheap + slow) to ensure non-trivial decisions.
Evidence: `inventory.json` · `suppliers.json`

---

## By DL

| DL | Methods used | Key evidence files |
|----|--------------|--------------------|
| DL-01 | Lab · Workshop | `inventory.json` · `suppliers.json` · `stockout_warning.json` · `duplicate_invoice.json` · `state.py` |
| DL-02 | Library · Showroom · Lab | `graph.py` · `decide.py` · `inventory_monitor.py` · `supplier_scout.py` · `invoice_auditor.py` · `llm.py` · `api_client.py` · `PIPELINE_ARCHITECTURE.md` · `ORCHESTRA_ARCHITECTURE.md` |
| DL-03 | Library · Showroom | `docs/user_requirements.md` · `docs/wireframes.md` · `dashboard/wireframe.html` · `images/dl03-wireframe-comparison.png` |
| DL-04 | Lab · Field | `dashboard/betsy.html` · `shared/llm.py` · `pipeline/nodes/decide.py` · `images/dl04-pipeline-first-run.png` |
| DL-05 | Lab | `server/routers/approvals.py` · `pipeline/nodes/act.py` · `server/state.py` · `docs/test-report-dl05.md` |
| DL-06 | Lab | `server/db.py` · `tests/test_ema_learning.py` · `docs/test-report-dl06.md` |
| DL-07 | Lab | `tests/test_long_term_learning.py` · `pipeline/nodes/evaluate.py` |
| DL-08 | Lab | `server/notifier.py` · `tests/test_notifier.py` · `server/config.py` |
