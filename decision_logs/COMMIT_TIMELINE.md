# Betsy — Commit Timeline

Chronological build history mapped to project phases and decision logs.

---

## Phase 0 — Environment setup

`2525b43` — `Initial commit: Betsy procurement agent test environment`
Starting point: mock datasets (12 SKUs, 6 suppliers, 15 invoices), FastAPI
server, 4 injectable scenarios, and a live procurement dashboard. Everything
the agent would need to test against — before any agent code existed.
→ DL-01

`f684cf8` — `Add BPM analysis: before/after process model for Betsy agent`
Standalone HTML document (`bpm_analysis.html`) with swimlane diagrams showing
the AS-IS manual procurement workflow vs the TO-BE agentic AI-augmented
process. Includes 3- and 4-lane diagrams, scenario walkthroughs (stockout,
duplicate invoice, price spike), and a weekly time-motion analysis.
→ Pre-DL-02 / supports DL-01 framing

---

## Phase 1 — Agent architecture

`c722d87` — `Add agent architecture: Pipeline, Orchestra, compare runner, and shared utilities`
Both agent architectures committed together: LangGraph Pipeline (6-node
sequential) and Orchestra (3 parallel agents + coordinator). Shared utilities
(`llm.py`, `api_client.py`, `state.py`) written once and used by both.
→ DL-02

`1daaba0` *(merge)* — `Merge pull request #1 from YashAlwani/agent-architecture`
Architecture branch merged into main.

`9fd7ab7` — `Add analysis segments and decision logs (DL-01, DL-02)`
DL-01 and DL-02 written and committed alongside the architecture code.
Evidence files (`inventory.json`, `suppliers.json`, `graph.py`, `decide.py`,
`PIPELINE_ARCHITECTURE.md`, `ORCHESTRA_ARCHITECTURE.md`) added to
`decision_logs/evidence/`.
→ DL-01 · DL-02

---

## Phase 2 — UI and live integration

`a737cac` — `remove: delete Streamlit dashboard, replaced by betsy.html`
Streamlit prototype removed. The Flask/Jinja dashboard was replaced by a
plain HTML approach served directly from FastAPI — no build step, no
framework dependency.

`8d9f213` — `feat: add Betsy AI layer UI, docs, model switch to llama3.1:8b`
betsy.html wired to the live FastAPI endpoints. POST /api/run-agent added as
a background task trigger. Model switched from Mistral 7B to Llama 3.1 8B
for better structured JSON output. AI narrative, ✦ Risk column, and ✦ Betsy
Score column all pulling from the live API.
→ DL-04

`4282f35` — `add DL-03, DL-04, DL-SUMMARY and all screenshots/evidence`
DL-03 (UI design) and DL-04 (implementation and first real run) written.
All screenshots for both DLs added to `decision_logs/images/`. DL-SUMMARY
first version committed.
→ DL-03 · DL-04

---

## Phase 3 — HITL approval queue

`2733e53` — `feat: DL-05 HITL approval queue — full approve/decline loop`
/api/approvals router built (GET pending, POST approve, POST reject).
act.py stores the full PO payload at queue time and executes it on approval.
betsy.html approval cards wired to real endpoints.
→ DL-05

`e28613d` — `fix: don't clear approvals on scenario reset — approvals survive until user acts`
Bug found during DL-05 testing: state.reset() was wiping the approval queue
at the end of every pipeline run. Single-line fix — approvals kept independent
of scenario state.
→ DL-05

`457f41a` — `docs: DL-05 test report — 11/11 passed, bug fix documented`
Test report for the 11-case approval queue test suite committed to
`docs/test-report-dl05.md`. Bug and fix documented within the report.
→ DL-05

`f78a75f` — `docs: write DL-05 — HITL approval queue, bug doc, integration notes`
DL-05 decision log written.
→ DL-05

`ef39d1a` *(merge)* — `merge: DL-05 HITL approval queue`

---

## Phase 4 — Persistence, learning, and scheduling

`fba4d06` — `feat: DL-06 persistence, EMA learning, APScheduler, stats panel`
Three gaps closed in one sprint: SQLite persistence via `server/db.py`
(agent_log + approvals survive restarts), EMA supplier scoring triggered on
PO delivery (α=0.2), APScheduler BackgroundScheduler firing the pipeline
every 30 minutes, stats endpoint + betsy.html stats panel.
→ DL-06

`3df6380` — `docs: DL-06 test report — 9/9 passed, EMA formula verified`
Test report committed. Restart verification (T4) and both EMA formula checks
(T5a, T5b) documented with exact predicted vs actual values.
→ DL-06

`5ccead0` — `feat: add preserve_scores, score PATCH endpoint, magnus opus test, run_server script`
PATCH endpoint for supplier scores added to `server/routers/suppliers.py`.
preserve_scores mechanism added for test isolation. Long-term learning
integration test (`test_long_term_learning.py`) built — two real LLM pipeline
runs with 8 delivery simulation rounds between them. run_server.py script
added for convenience.
→ DL-07

`9b8e7f7` — `docs: add DL-06 and DL-07 decision logs`
DL-06 and DL-07 written.
→ DL-06 · DL-07

`0d7dedb` — `polish all DLs: remove inline code blocks, replace with casual file references`
Formatting pass across all DLs — inline code blocks replaced with plain file
references for readability.

`cdaad08` — `docs: add README`

`bf8bd10` *(merge)* — `Merge pull request #2 from YashAlwani/feat/dl06-persistence-learning`

---

## Phase 5 — Push notifications

`6cdd95e` — `feat: add desktop and email push notifications (DL-08)`
Two-channel notification system added from scratch — no predecessor code
existed. Desktop toasts via plyer (optional dependency), HTML emails via
smtplib (stdlib). All logic in `server/notifier.py`. Settings panel added to
betsy.html. Runtime config via POST /api/notifications/config backed by
mutable module-level attributes in `server/config.py`. 22/22 unit tests
passing.
→ DL-08

---

## At a glance

| Phase | Key deliverable | DL |
|-------|-----------------|-----|
| Environment | Mock data + FastAPI server + dashboard | DL-01 |
| Analysis | BPM as-is / to-be swimlane diagrams | — |
| Architecture | Pipeline + Orchestra + shared utilities | DL-02 |
| UI | betsy.html live integration, model switch | DL-03 · DL-04 |
| HITL | Approval queue end-to-end, bug fix, 11/11 tests | DL-05 |
| Persistence | SQLite + EMA scoring + APScheduler | DL-06 |
| Learning | Long-term learning integration test | DL-06 · DL-07 |
| Notifications | Desktop + email push, settings panel, 22 tests | DL-08 |
