# Code Evidence — `@token` → code snippet map

**Purpose.** Some `@token`s in the decision logs point at **code that proves an
implementation claim** (a constant, a function, an endpoint, a test). This
document is the screenshot guide for those tokens only. For each one it records:

- the **decision log** it appears in,
- the **`@token`** and the **first and last sentence** where that token is used in the prose,
- the **code file** and the **exact line range** to capture,
- a **description** of what the snippet shows, so a screenshot can be captioned without re-reading the code.

**Scope.** Only tokens that resolve to *code or data files* are listed
(`.py`, `.html`, `.json`, `.txt`). Tokens for diagrams (`@gap-as-is`,
`@decision-lifecycle`, …), PDFs and design docs (`@bpm_analysis`,
`@case_summary`, `@api-control-layer`, …) are evidence of *reasoning*, not
*implementation*, and are deliberately excluded. Line numbers are 1-based and
match the files on branch `docs/evidence-tokens-lifecycle`.

> Format per entry:
> **Decision log** · **`@token`** · *"first sentence … last sentence"* · **file** `folder/file` · **lines `###-###`** · **Description**

---

## DL-01 — Building the mock environment

### `@inventory`
- **Sentence(s):** *"The inventory data @inventory holds the 12 SKUs, and each one carries a reorder point and an average daily usage."* (single inline use; also in `Files:` footer)
- **File:** `mock_data/inventory.json`
- **Lines:** `1-146` (representative single SKU: `2-13`; the two required fields are `reorder_point` at `7` and `daily_usage_avg` at `9`)
- **Description:** The 12-SKU dataset. Each object carries `reorder_point` and `daily_usage_avg` — the two numbers the stockout maths (days-remaining = stock ÷ daily usage) depends on.

### `@suppliers`
- **Sentence(s):** *"The supplier data @suppliers gives each supplier a different price, lead time, and reliability score."*
- **File:** `mock_data/suppliers.json`
- **Lines:** `1-81`
- **Description:** Six suppliers, each with a `reliability_score` and a per-SKU `catalog` of `unit_price` / `lead_days` — the deliberate price-vs-speed-vs-reliability trade-offs that make supplier selection a real decision.

### `@scenarios`
- **Sentence(s):** *"The scenario files @scenarios each describe one problem and the action the agent should take."*
- **File:** `scenarios/` (folder: `stockout_warning.json`, `price_spike.json`, `duplicate_invoice.json`, `supplier_oos.json`)
- **Lines:** representative `scenarios/stockout_warning.json` `1-16`
- **Description:** Each scenario file patches the base state via `overrides` and declares an `expected_agent_action` / `expected_supplier` — i.e. each problem ships with its known-correct answer for checking.

### `@state` (scenario injection)
- **Sentence(s):** *"The scenario injection @state applies a scenario by copying the base state and patching only the relevant fields."* … *"the base state is copied on every injection (@state)."*
- **File:** `server/state.py`
- **Lines:** `43-88` (key line: the `deepcopy(self._base)` at `54`)
- **Description:** `apply_scenario()` deep-copies the pristine base state, then patches only the overridden inventory/supplier/invoice fields — so every run starts from the same clean baseline and runs never contaminate each other.

---

## DL-02 — Pipeline vs Orchestra architecture

### `@pipeline-graph`
- **Sentence(s):** *"The Pipeline came first — six nodes, ingest then detect then evaluate then decide then act then audit, with one typed state object passed through each node (@pipeline-graph)."*
- **File:** `pipeline/graph.py`
- **Lines:** `13-31`
- **Description:** The LangGraph `build()` that wires the six nodes in a fixed sequence (`ingest → detect → evaluate → decide → act → audit → END`), all sharing one typed `PipelineState`.

### `@decide` (hardcoded spending cap)
- **Sentence(s):** *"That is a business rule, not an AI judgement, and it is written as a constant in code (@decide)."* … *"the spending limit is a Python constant in the decide node, not a sentence in a system prompt (@decide)."*
- **File:** `pipeline/nodes/decide.py`
- **Lines:** `12` (the `MAX_AUTO_USD` constant) **and** `115-119` (enforcement)
- **Description:** `MAX_AUTO_USD = float(os.getenv("MAX_AUTO_USD", "5000"))` is the hard limit; lines 117-118 force `requires_human = True` when `po_total > MAX_AUTO_USD`, with the comment "financial safeguard cannot be overridden" — proving the cap is code, not a prompt the model can talk past.

### `@orchestra-graph` (precedence table)
- **Sentence(s):** *"…feeds their findings to a central orchestrator that applies a conflict-precedence table before anything executes (@orchestra-graph)."* … *"the Orchestra precedence table blocks the purchase order while a duplicate invoice is active (@orchestra-graph)."*
- **File:** `orchestra/graph.py`
- **Lines:** `23-28` (the `PRECEDENCE` table) **plus** `99-143` (conflict detection in `orchestrate_node`) and `287-303` (the five-stage `build()`)
- **Description:** The hardcoded `PRECEDENCE` dict — duplicate-invoice beats stockout, price-spike beats stockout — applied in `orchestrate_node` *before* `execute`, so a duplicate invoice blocks the related PO by rule rather than by model judgement.

### `@inventory_monitor`
- **Sentence(s):** *"Orchestra runs three specialist agents in parallel — inventory_monitor, supplier_scout, and invoice_auditor (@inventory_monitor · @supplier_scout · @invoice_auditor) …"*
- **File:** `orchestra/agents/inventory_monitor.py`
- **Lines:** `18-83`
- **Description:** Specialist agent #1: scans inventory, emits `stockout_risk` findings with urgency/confidence. Read-only (works from the shared brief).

### `@supplier_scout`
- **Sentence(s):** (same parallel-agents sentence as above)
- **File:** `orchestra/agents/supplier_scout.py`
- **Lines:** `20-138` (price-spike threshold constant at `17`)
- **Description:** Specialist agent #2: scores suppliers (`reliability / lead_days`), detects price spikes (>30%) and unavailability, and LLM-ranks options for critical SKUs.

### `@invoice_auditor`
- **Sentence(s):** (same parallel-agents sentence as above)
- **File:** `orchestra/agents/invoice_auditor.py`
- **Lines:** `18-111` (duplicate-pair matcher `_find_duplicates` at `80-111`)
- **Description:** Specialist agent #3: finds duplicate invoice pairs (same supplier, same amount, ≤60 days apart) and LLM-classifies fraud vs billing error.

### `@llm`
- **Sentence(s):** *"Both patterns use the same LLM client and the same API layer, so they are interchangeable at the run level (@llm · @api_client)."*
- **File:** `shared/llm.py`
- **Lines:** `1-46` (client + model config `8-17`; JSON-with-fallback `20-33`)
- **Description:** The single shared Ollama client both Pipeline and Orchestra call. `call_json()` returns `{fallback: True}` on any parse failure instead of raising.

### `@api_client`
- **Sentence(s):** (same shared-client sentence as above)
- **File:** `shared/api_client.py`
- **Lines:** `1-95`
- **Description:** The shared HTTP layer (offline JSON loaders + live `/api/...` calls) used by both architectures, so they are interchangeable at run level.

### `@pipeline-state`
- **Sentence(s):** *"Both patterns use the same typed-state shape — each pattern keeps its own state file (@pipeline-state, @orchestra-state) …"*
- **File:** `pipeline/state.py`
- **Lines:** `5-22`
- **Description:** The `PipelineState` TypedDict — the typed object passed node-to-node through the pipeline.

### `@orchestra-state`
- **Sentence(s):** (same typed-state sentence as above)
- **File:** `orchestra/state.py`
- **Lines:** `5-22`
- **Description:** The `OrchestraState` TypedDict — the parallel-pattern equivalent (brief + per-agent findings + conflicts/decisions).

---

## DL-03 — The user-facing AI layer (design → prototype)

### `@wireframe`
- **Sentence(s):** *"The Showroom phase was building @wireframe — a fully interactive HTML prototype with working navigation, approve and decline buttons, expandable log entries, and a live badge counter."*
- **File:** `dashboard/wireframe.html`
- **Lines:** `1-799` (interaction proof: approve/decline buttons `551-555`; nav badge `422`)
- **Description:** The static-data interactive prototype: four screens, working approve/decline handlers, and a live approval badge — used to validate layout before wiring real data.

### `@betsy`
- **Sentence(s):** *"…@betsy and @index are two separate files served from the same server."*
- **File:** `dashboard/betsy.html`
- **Lines:** `1-1484` (served at the `/betsy` route — see `server/main.py:73-75`)
- **Description:** Betsy's AI-layer surface — a separate file from the dev dashboard, served from the same FastAPI server.

### `@index`
- **Sentence(s):** *"The environment (@index) is unchanged; Betsy reads from and writes to the same API any human operator would use."*
- **File:** `dashboard/index.html`
- **Lines:** `1-619` (served at `/` — see `server/main.py:68-70`)
- **Description:** The unchanged procurement/dev dashboard. Proof that Betsy is a *layer*, not a replacement — both pages hit the same API.

---

## DL-04 — Wiring to live data, model selection, the safeguard in action

### `@betsy` — live data fetch
- **Sentence(s):** *"The implementation started with the connection question: how does @betsy talk to the server?"* … *"A single Promise.all pulls inventory, suppliers, and the agent log in one shot, same origin, no CORS to fight."*
- **File:** `dashboard/betsy.html`
- **Lines:** `1343-1356` (the `Promise.all`); helper `fetch` at `906-924`; 5-second auto-refresh at `1378`
- **Description:** `refresh()` pulls inventory, suppliers, agent-log, approvals and stats in one `Promise.all`, same origin. `setInterval(refresh, 5000)` is the five-second poll.

### `@betsy` — browser-side narrative (~20 lines JS)
- **Sentence(s):** *"The AI narrative is generated in the browser from that same data — no model call needed for the summary."* … *"That is about twenty lines of plain JavaScript in @betsy."*
- **File:** `dashboard/betsy.html`
- **Lines:** `983-1017`
- **Description:** `buildNarrative()` — the ~20 lines that turn live inventory + agent-log into the plain-English summary ("…was critically low — I've already placed the order automatically.") with no LLM call.

### `@betsy` — scenario chips trigger the run
- **Sentence(s):** *"The scenario chips on Betsy's page post to this run-agent endpoint ¹@api-control-layer."* (footnote ¹ → `@main`)
- **File:** `dashboard/betsy.html`
- **Lines:** `1262-1265` (chip markup at `764-768`)
- **Description:** The Run-Betsy handler POSTs `/api/run-agent?mode=pipeline&scenario=…`; the chips at 764-768 set the selected scenario.

### `@index` — plain fetch pattern
- **Sentence(s):** *"@index uses plain fetch() calls against the API — no framework, no build step — and @betsy follows the same pattern."*
- **File:** `dashboard/index.html`
- **Lines:** `310-314` (the `api()` fetch helper) and `580-591` (its `Promise.all`); 3-second poll at `610`
- **Description:** The dev dashboard's fetch helper — vanilla `fetch`, no framework — which Betsy's page mirrors.

### `@llm` — model default switched to Llama 3.1 8B
- **Sentence(s):** *"@llm already handles malformed JSON with a fallback …"* … *"configurable by environment variable and defaulting to llama3.1:8b (@llm)."*
- **File:** `shared/llm.py`
- **Lines:** `8-9` (`OLLAMA_MODEL` default `llama3.1:8b`) and `20-33` (malformed-JSON fallback)
- **Description:** `OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")` — env-configurable default; `call_json` falls back to `{fallback: True}` on bad JSON rather than crashing.

### `@decide` — the $5,000 safeguard firing
- **Sentence(s):** *"The safeguard in the decide node checks the order total against the $5,000 autonomous spending limit and flips the decision to human review when it is exceeded … and that flag cannot be overridden by model reasoning (@decide)."*
- **File:** `pipeline/nodes/decide.py`
- **Lines:** `77` (`po_total`), `115-119` (override), `100-113` (rule-based fallback path also enforces it)
- **Description:** The exact lines that compute `po_total` and force human review above the cap — the reason the $11,937 SKU-003 order came back `pending_human_review`.

### `@main` (footnote ¹) — the run-agent endpoint
- **Sentence(s):** footer `¹@main`, bridging the body's *"post to this run-agent endpoint ¹@api-control-layer."*
- **File:** `server/main.py`
- **Lines:** `78-87`
- **Description:** `POST /api/run-agent` hands the pipeline to FastAPI `BackgroundTasks` and returns immediately, so the browser does not hang on the model call.

---

## DL-05 — The human-in-the-loop approval queue

### `@approvals`
- **Sentence(s):** *"Build the approvals API as a standalone router with three endpoints — list pending, approve, reject …"* … *"The approve endpoint in @approvals picks that payload up, creates the PO directly in state, and logs the human decision (@act)."*
- **File:** `server/routers/approvals.py`
- **Lines:** `12-14` (list), `36-90` (approve), `93-116` (reject); PO build at `49-77`
- **Description:** The three-endpoint approvals router. `approve()` pulls the pre-built payload, creates the PO directly in `state.purchase_orders` with `requested_by = "betsy-human-approved"`, and writes the human decision to the log.

### `@act`
- **Sentence(s):** *"The act node builds the complete PO payload the moment a decision is made — supplier, SKU, quantity, unit price, reasoning — and passes the whole thing to the approval queue."*
- **File:** `pipeline/nodes/act.py`
- **Lines:** `28-58` (`_queue_for_approval` builds the full payload) and `61-75` (queues whenever not auto-approved)
- **Description:** The act node assembles the complete PO payload at queue time (nothing recomputed on approval) and posts it to `/api/approvals`.

### `@state` — the reset bug
- **Sentence(s):** *"I traced it to the reset() function in @state — one line was wiping the approvals at the end of every pipeline run …"* … *"Removing that single line fixed it."*
- **File:** `server/state.py`
- **Lines:** `36-41` (the `reset()` method)
- **Description:** `reset()` clears the scenario state and agent log — but must **not** touch `self.approvals` (those are user-facing decisions, not mock data). The removed line was the bug.

### `@api_client` — swallowed error
- **Sentence(s):** *"If the server is down and someone triggers the pipeline straight from the terminal, the approval fails quietly and the decision is lost — @api_client swallows the error."*
- **File:** `shared/api_client.py`
- **Lines:** `81-86` (`queue_approval`)
- **Description:** `queue_approval()` wraps the POST in try/except and returns `{queued: False}` on failure — the silent-loss path called out as a known limit.

---

## DL-06 — Persistence, learning, scheduling

### `@db`
- **Sentence(s):** *"SQLite persistence through a new @db module using Python's built-in database support …"* … *"All writes go through one lock in @db."*
- **File:** `server/db.py`
- **Lines:** `7-46` (`DB_PATH`, the single `_lock`, `init_db` schema for `agent_log` + `approvals`); write paths `51-64`, `90-111`
- **Description:** The SQLite persistence module — one `threading.Lock` guarding all writes, two tables created on first start, no external service.

### `@state` — reload on boot
- **Sentence(s):** *"On start-up the state loads both tables back into memory, so the log entries and approvals return exactly as they were before the restart (@state · @db)."*
- **File:** `server/state.py`
- **Lines:** `12-23` (`AppState.__init__`)
- **Description:** On construction the state calls `db.init_db()` then reloads `agent_log` and `approvals` from SQLite — the lines that make the queue survive a restart.

### `@orders` — EMA score update
- **Sentence(s):** *"The update fires in @orders the moment an order is marked delivered: the router reads the expected and actual dates, works out the lateness, and updates the supplier's score in place."*
- **File:** `server/routers/orders.py`
- **Lines:** `10` (`EMA_ALPHA = 0.2`), `70-82` (delivered → `_apply_ema`), `85-104` (the formula)
- **Description:** `_apply_ema` computes `performance = max(0, 1 − lateness×0.1)` then `new = 0.2·performance + 0.8·old`, rounded to 4 dp — the exact formula DL-06/07 verify.

### `@scheduler_instance`
- **Sentence(s):** *"…a tiny @scheduler_instance module to solve a circular-import problem …"* … *"The scheduler lives in its own three-line module, @scheduler_instance, rather than in @main."*
- **File:** `server/scheduler_instance.py`
- **Lines:** `1-3`
- **Description:** The three-line singleton (`scheduler = BackgroundScheduler()`) that both `main` and `stats` import — breaking the circular import cleanly.

### `@main` — scheduler lifecycle
- **Sentence(s):** *"The start-up routine in @main starts the scheduler, registers the pipeline job with the chosen interval, and shuts it down on exit."*
- **File:** `server/main.py`
- **Lines:** `27-40` (the `lifespan` context manager); job runner `19-24`
- **Description:** `lifespan()` adds the `betsy_auto_run` interval job (default 30 min, `AGENT_INTERVAL_MINUTES`), starts the scheduler, and shuts it down on exit.

### `@stats`
- **Sentence(s):** *"The stats reading works everything out from the current state and the scheduler at the moment it is asked … refreshing on the same five-second poll as the rest of the dashboard (@stats)."*
- **File:** `server/routers/stats.py`
- **Lines:** `9-44`
- **Description:** `GET /api/stats` derives the five figures (total decisions, autonomous rate, pending approvals, queue value, next run) from live state + the scheduler's `next_run_time`.

### `@test_ema_learning`
- **Sentence(s):** *"…PrecisionParts GmbH moved from 0.97 to 0.9760 on time and to 0.8808 after a five-day-late delivery, both matching the formula exactly and confirmed by @test_ema_learning."*
- **File:** `tests/test_ema_learning.py`
- **Lines:** `50-110` (the `ema_expected` helper + the two delivery checks)
- **Description:** The script that drives one on-time and one 5-day-late delivery against SUP-004 and asserts the score matches `0.9760` then `0.8808`.

---

## DL-07 — Proving learning changes the decision

### `@test_long_term_learning`
- **Sentence(s):** *"Build a standalone integration test — @test_long_term_learning — that runs two complete pipeline calls with a structured set of deliveries between them."* … *"Run @test_long_term_learning to produce side-by-side evidence of delivery history changing the recommendation …"*
- **File:** `tests/test_long_term_learning.py`
- **Lines:** `36-46` (the 8-round `ROUNDS` schedule) and `174-336` (the two-run / deliver / compare flow)
- **Description:** The integration test: run #1 (baseline) → 8 deliveries (QuickShip 5×8-days-late, FastParts 3×on-time) → restore learned scores → run #2, then compare the chosen supplier.

### `@evaluate`
- **Sentence(s):** *"The composite score in @evaluate divides a supplier's reliability by its lead time for the target SKU …"* … *"The ranking is worked out in @evaluate and passed straight to the model."*
- **File:** `pipeline/nodes/evaluate.py`
- **Lines:** `40-43` (`_score_supplier` = `reliability / lead_days`), `46-74` (ranking + the `ranked_info` list sent to the model)
- **Description:** The composite-score function and the ranked-supplier list that becomes the model's main input — the place where a changed score changes the ranking the model sees.

### `@suppliers-router` — score-restore endpoint
- **Sentence(s):** *"…so I added a dedicated endpoint for setting supplier scores and called it explicitly after each scenario injection — deterministic, with no parsing ambiguity."* (footer `@suppliers-router`)
- **File:** `server/routers/suppliers.py`
- **Lines:** `21-29` (`PATCH /api/suppliers/{id}/score`)
- **Description:** The dedicated score-setting endpoint added in DL-07 so learned scores can be restored deterministically before run #2.

---

## DL-08 — Push notifications

### `@notifier`
- **Sentence(s):** *"All the sending logic lives in @notifier."* … *"The notifier reads its settings from the config at the moment it is called, not when it is first loaded."*
- **File:** `server/notifier.py`
- **Lines:** `17-51` (the `_desktop` / `_email` send helpers) and `86-205` (the public `notify_*` functions, each reading `config.*` at call time)
- **Description:** Fire-and-forget dispatch: desktop via plyer (silent if missing), email on a background thread, every send wrapped so a failure can't break a run.

### `@config`
- **Sentence(s):** *"The settings live in @config as plain module values that are read from environment variables at start-up and can be changed at runtime through a settings endpoint …"*
- **File:** `server/config.py`
- **Lines:** `13-30` (module-level settings incl. `SCORE_DROP_THRESHOLD`) and `33-52` (`update()`)
- **Description:** Plain module-level values (not frozen constants) so `update()` can mutate them at runtime; `update()` type-coerces known keys and ignores unknown ones.

### `@decide` — notification trigger points
- **Sentence(s):** *"…all four approval triggers … are marked as not auto-approved in the decide node …"* … *"I confirmed this in the decide node, where the duplicate flag, the price spike, and the escalation are each marked not auto-approved."*
- **File:** `pipeline/nodes/decide.py`
- **Lines:** `38-66` (duplicate / price-spike / escalate all set `"auto_approved": False`)
- **Description:** The branches that mark every human-review case `auto_approved: False`, so all of them flow through `act` → the approval queue → a single notification point.

### `@approvals` — fires the approval notification
- **Sentence(s):** *"…the approvals router sends the approval notification the moment the item is saved, with the action mapped to a readable label …"*
- **File:** `server/routers/approvals.py`
- **Lines:** `28-33` (`notify_approval_required(item)` inside `queue_approval`)
- **Description:** The single point that fires the desktop+email approval alert as an item is saved to the queue.

### `@orders` — auto-order and score-drop alerts
- **Sentence(s):** *"…the orders router sends the score-drop alert only on the first crossing of the warning line …"* and *"…the orders router sends the auto-order alert when the order came from the pipeline itself …"*
- **File:** `server/routers/orders.py`
- **Lines:** `64-65` (`notify_auto_approved` when `requested_by == "betsy-pipeline"`) and `106-112` (score-drop alert only on first crossing of `SCORE_DROP_THRESHOLD`)
- **Description:** The two order-side triggers: auto-approved-PO alert, and the score-drop alert gated on `new < threshold and old >= threshold` (crossing, not every late delivery).

### `@notifications-router` — runtime settings endpoint
- **Sentence(s):** *"…can be changed at runtime through a settings endpoint …"* (footer `@notifications-router`)
- **File:** `server/routers/notifications.py`
- **Lines:** `8-22` (GET config), `25-45` (POST config → `config.update`), `48-58` (test)
- **Description:** The endpoints that read/update notification settings at runtime and send a test message — what the dashboard panel talks to.

### `@betsy` — the settings panel
- **Sentence(s):** *"…and a settings panel was added to @betsy."* … *"@betsy now has a collapsible Notifications panel with the mail fields and a toggle per trigger."*
- **File:** `dashboard/betsy.html`
- **Lines:** `777-819` (panel markup) and `1410-1465` (`saveNotifSettings` / `sendTestNotification` → `/api/notifications/config` and `/test`)
- **Description:** The collapsible Notifications panel: mail fields, a chip per trigger, Save + Send-test buttons posting to the notifications router.

### `@test_notifier`
- **Sentence(s):** *"The whole suite runs in well under a second, and all 22 passed (@test_notifier)."*
- **File:** `tests/test_notifier.py`
- **Lines:** `1-261` (desktop tests `44-84`, email tests `89-134`, per-notification tests `139-229`, config-update tests `234-257`)
- **Description:** The 22 mocked tests (nothing real sent): desktop on/off/trim/swallow, email headers/silence/thread/swallow, each toggle, and config type-coercion.

### `@requirements` — optional dependency
- **Sentence(s):** *"Desktop toasts go through plyer, an optional library that quietly does nothing if it is not installed."* (footer `@requirements`)
- **File:** `requirements.txt`
- **Lines:** `11` (`plyer>=2.1.0`) — `apscheduler` at `10`, `python-dotenv` at `5`
- **Description:** `plyer` is the only desktop-notification dependency; email uses the standard library, so no new *required* dependency was added.

---

## Quick index (token → file → lines)

| `@token` | DL(s) | File | Lines |
|----------|-------|------|-------|
| `@inventory` | 01 | `mock_data/inventory.json` | 1-146 |
| `@suppliers` | 01 | `mock_data/suppliers.json` | 1-81 |
| `@scenarios` | 01 | `scenarios/stockout_warning.json` (repr.) | 1-16 |
| `@state` (inject) | 01 | `server/state.py` | 43-88 |
| `@state` (reset bug) | 05 | `server/state.py` | 36-41 |
| `@state` (boot reload) | 06 | `server/state.py` | 12-23 |
| `@pipeline-graph` | 02 | `pipeline/graph.py` | 13-31 |
| `@decide` (cap) | 02, 04 | `pipeline/nodes/decide.py` | 12, 115-119 |
| `@decide` (triggers) | 08 | `pipeline/nodes/decide.py` | 38-66 |
| `@orchestra-graph` | 02 | `orchestra/graph.py` | 23-28, 99-143 |
| `@inventory_monitor` | 02 | `orchestra/agents/inventory_monitor.py` | 18-83 |
| `@supplier_scout` | 02 | `orchestra/agents/supplier_scout.py` | 17, 20-138 |
| `@invoice_auditor` | 02 | `orchestra/agents/invoice_auditor.py` | 18-111 |
| `@llm` | 02, 04 | `shared/llm.py` | 8-17, 20-33 |
| `@api_client` | 02 | `shared/api_client.py` | 1-95 |
| `@api_client` (swallow) | 05 | `shared/api_client.py` | 81-86 |
| `@pipeline-state` | 02 | `pipeline/state.py` | 5-22 |
| `@orchestra-state` | 02 | `orchestra/state.py` | 5-22 |
| `@wireframe` | 03 | `dashboard/wireframe.html` | 551-555, 422 |
| `@betsy` (separate file) | 03 | `dashboard/betsy.html` | served `/betsy` |
| `@betsy` (Promise.all) | 04 | `dashboard/betsy.html` | 1343-1356 |
| `@betsy` (narrative) | 04 | `dashboard/betsy.html` | 983-1017 |
| `@betsy` (run chips) | 04 | `dashboard/betsy.html` | 764-768, 1262-1265 |
| `@betsy` (settings panel) | 08 | `dashboard/betsy.html` | 777-819, 1410-1465 |
| `@index` (unchanged) | 03 | `dashboard/index.html` | served `/` |
| `@index` (fetch) | 04 | `dashboard/index.html` | 310-314, 580-591 |
| `@main` (run-agent) | 04 | `server/main.py` | 78-87 |
| `@main` (scheduler) | 06 | `server/main.py` | 27-40 |
| `@approvals` | 05 | `server/routers/approvals.py` | 36-90 |
| `@approvals` (notify) | 08 | `server/routers/approvals.py` | 28-33 |
| `@act` | 05 | `pipeline/nodes/act.py` | 28-75 |
| `@db` | 06 | `server/db.py` | 7-46 |
| `@orders` (EMA) | 06 | `server/routers/orders.py` | 10, 85-104 |
| `@orders` (notify) | 08 | `server/routers/orders.py` | 64-65, 106-112 |
| `@scheduler_instance` | 06 | `server/scheduler_instance.py` | 1-3 |
| `@stats` | 06 | `server/routers/stats.py` | 9-44 |
| `@test_ema_learning` | 06 | `tests/test_ema_learning.py` | 50-110 |
| `@test_long_term_learning` | 07 | `tests/test_long_term_learning.py` | 36-46, 174-336 |
| `@evaluate` | 07 | `pipeline/nodes/evaluate.py` | 40-74 |
| `@suppliers-router` | 07 | `server/routers/suppliers.py` | 21-29 |
| `@notifier` | 08 | `server/notifier.py` | 17-51, 86-205 |
| `@config` | 08 | `server/config.py` | 13-30, 33-52 |
| `@notifications-router` | 08 | `server/routers/notifications.py` | 25-45 |
| `@test_notifier` | 08 | `tests/test_notifier.py` | 1-261 |
| `@requirements` | 08 | `requirements.txt` | 11 |
