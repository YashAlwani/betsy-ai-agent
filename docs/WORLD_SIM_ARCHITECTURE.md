# World Simulator Architecture — Betsy v2

**Status:** Approved design, implementation in progress on `feat/world-sim`
**Date:** 2026-07-29
**Supersedes:** the scenario-injection mock server described in `api-control-layer.md`

---

## 1. Problem statement

The POC that got us through DL-01…DL-08 has three structural limitations that block the next
learning objectives:

1. **The world is frozen.** All ERP state lives in one in-memory `AppState`
   (`server/state.py`) rebuilt from `mock_data/*.json`. Nothing consumes stock, nothing
   delivers a PO, nothing issues an invoice. `daily_usage_avg` is a read-only prop. Every
   agent run re-detects the identical situation forever.
2. **The learning loop is unreachable.** Supplier EMA scoring (`_apply_ema`, formerly in
   `server/routers/orders.py`) only fires when a PO is manually PATCHed to `delivered` —
   which only the test scripts ever do. Scores live in memory, so even test-driven learning
   is wiped by a restart or a scenario reset.
3. **App and environment are entangled.** The same FastAPI process is simultaneously the
   simulated ERP *and* the Betsy application (agent runs, approvals, notifications,
   dashboards). "Scenarios" are destructive state resets, so demonstrating one capability
   erases the history behind another.

**Goal:** Betsy becomes a real application that runs the procurement lifecycle
autonomously and continuously; the environment becomes a separate, simulatable,
replaceable service.

---

## 2. Target architecture

```
┌────────────────────────────┐         ┌─────────────────────────────────┐
│  WORLD  (port 8001)        │         │  BETSY APP  (port 8000)         │
│  "Simulated ERP"           │         │                                 │
│                            │  HTTP   │  WorldClient (adapter)          │
│  world.db (SQLite)         │◄────────┤    ▲                            │
│   inventory                │         │    │                            │
│   suppliers (+hidden       │         │  agent_loop (clock poll)        │
│     true_reliability)      │         │    └─► orchestra (LangGraph     │
│   purchase_orders          │         │         multi-agent, Ollama)    │
│   invoices                 │         │  memory.py (EMA observer)       │
│   sim clock + events       │         │  approvals workflow             │
│                            │         │  notifier (desktop/email)       │
│  tick engine:              │         │  betsy.db (SQLite)              │
│   consume stock            │         │   agent_log, approvals,         │
│   progress deliveries      │         │   supplier_scores,              │
│   generate invoices        │         │   processed_deliveries,         │
│   fire events              │         │   agent_cursor                  │
│                            │         │  dashboards (/, /betsy)         │
└────────────────────────────┘         └─────────────────────────────────┘
```

The world never calls Betsy. Betsy polls the world — exactly how an agent would sit next
to a real ERP. Swapping `WorldClient` for a real ERP adapter is the intended migration
path, which is the main transferability argument for the two-service split.

### 2.1 Data ownership

| Data | Owner | Why |
|---|---|---|
| Inventory, catalogs, POs, invoices | **world.db** | Objective facts of the environment; a real ERP owns these. |
| Sim clock, event timeline, RNG seed | **world.db** | Simulation concerns; meaningless to a real deployment. |
| `true_reliability` per supplier | **world.db, never serialized** | Ground truth used only to generate delivery jitter. Betsy must *discover* reliability, not read it. |
| `reliability_score` (learned EMA) | **betsy.db** | It is the agent's memory. The world states what happened; Betsy decides what it means. Also fixes learning-wiped-on-restart. |
| Agent log, approvals queue, run cursor | **betsy.db** | Application state. |
| Notification config | Betsy env/config | Application behavior. |

### 2.2 API contract changes

- World supplier payload = `{supplier_id, name, availability, payment_terms, catalog}` —
  **no score field**. Betsy's `/api/suppliers` merges `reliability_score` from betsy.db so
  every existing consumer (supplier_scout matrix, orchestrator, dashboard scoreboard)
  keeps its field contract.
- Pending decisions exist only in Betsy's approvals table. The world only ever receives
  committed POs: `POST /api/purchase-orders` creates status `approved`. The
  `pending_approval` status is retired from world data.
- `GET /api/snapshot` returns inventory + suppliers + POs + invoices + clock in one
  transaction, so an agent brief can't be split across a tick boundary.

---

## 3. Simulated time

- **1 tick = 1 simulated day.** The world stores an integer `sim_day`.
- Every payload also emits ISO dates via `SIM_EPOCH + timedelta(days=sim_day)`
  (`SIM_EPOCH = 2026-01-01`), so existing date parsers (EMA lateness, invoice duplicate
  window, dashboard rendering) work unchanged. World-owned code paths never use
  `datetime.now()`.
- **Clock control:** `GET /api/clock`, `POST /api/clock/play | pause | step?days=N |
  speed?tick_seconds=X`. A background runner ticks every `tick_seconds` while `running`.
- **Determinism:** each tick derives its RNG as `random.Random(f"{seed}:{day}")` —
  restart-safe with no RNG state to persist, and unit-testable (same seed + same steps ⇒
  identical world).

### 3.1 Tick pipeline (single SQLite transaction)

1. `day += 1`
2. Apply due injected/scripted events (see §4)
3. Consume stock per SKU: `max(0, stock − round(gauss(daily_usage_avg, 0.25·avg)))`
4. Progress POs: `approved → in_transit` after order day; `arrival_day <= day →
   delivered` (`actual_day = day`, stock += qty) and auto-generate the matching invoice
   (small RNG chance of a duplicate or amount error — that's where audit findings come from)
5. Ambient events at low probability: price drift ±2%, rare supplier outage
6. Append a `tick_summary` event row for the dashboard feed

### 3.2 PO lifecycle and hidden reliability

At PO creation the world draws a hidden `arrival_day = expected_day +
jitter(true_reliability)`: on time with probability `r`, otherwise late by
`1 + int(expovariate(1.5))` days. This is the **only** place `true_reliability` is used.
Betsy observes only `expected_delivery` vs `actual_delivery` and must learn reliability
from outcomes — which is the whole point of the EMA memory.

```
PO:      approved ──► in_transit ──► delivered        (world-owned transitions)
Invoice: issued ──► (disputed | paid)                 (disputed set by Betsy via PATCH)
```

---

## 4. Events replace scenarios

The old `scenarios/*.json` were destructive overrides applied to a reset world. They
become **timeline event scripts** injected into the *running* simulation
(`world/scenarios/*.json`, injected via `POST /api/events/script/{name}`; single events
via `POST /api/events`).

Script format:

```json
{
  "name": "price_spike",
  "description": "SUP-001 raises SKU-003 prices sharply",
  "events": [
    {"day_offset": 0, "type": "price_change",
     "payload": {"supplier_id": "SUP-001", "sku_id": "SKU-003", "unit_price": 20.0}},
    {"day_offset": 0, "type": "stock_set",
     "payload": {"sku_id": "SKU-003", "current_stock": 150}}
  ]
}
```

Event types: `price_change`, `stock_set`, `usage_spike`, `supplier_outage`
(with optional `duration_days` auto-restore), `duplicate_invoice`, `invoice_error`.
`day_offset` is relative to the current sim day at injection time.

Conversions of the four legacy scenarios:

| Legacy scenario | Event script |
|---|---|
| `stockout_warning` | `stock_set` (low stock) + `usage_spike` |
| `price_spike` | `price_change` × affected suppliers + `stock_set` |
| `duplicate_invoice` | `duplicate_invoice` event at offset 0 |
| `supplier_oos` | `supplier_outage` with `duration_days` |

---

## 5. The agent lifecycle loop

Betsy's APScheduler polls the world clock every few real seconds:

```
if clock.day >= last_run_day + AGENT_RUN_EVERY_DAYS and not run_lock.locked():
    memory.observe_deliveries()   # EMA learning from newly delivered POs
    orchestra.run.run_full()      # detect → decide → act → audit
    update agent_cursor
```

- **Coalescing:** a multi-day jump (fast-forward, step 10) produces one run, not ten.
- **Run lock:** an Ollama-backed orchestra run can take 30–60 s; ticks continue meanwhile.
  The dashboard shows a "Betsy is thinking (day N)" state.
- **Orchestra is the production agent** (fan-out multi-agent graph). The linear
  `pipeline/` remains as a comparison artifact from DL-04.

### 5.1 EMA observer (`server/memory.py`)

For each `delivered` PO not yet in `processed_deliveries`:
`lateness = max(0, actual − expected)` days →
`performance = max(0, 1 − 0.1·lateness)` →
`score = 0.2·performance + 0.8·old` (EMA α = 0.2, logic ported unchanged from the old
`orders.py:_apply_ema`). Unknown suppliers start at a **neutral prior 0.8**. The first
observe pass bootstraps from the seeded historical delivered POs. Score-drop
notifications keep the existing threshold-crossing behavior.

### 5.2 Safety gates (unchanged in spirit, relocated)

- `MAX_AUTO_USD = 5000` — larger POs always require human approval.
- Price spikes, duplicate invoices, supplier escalations always require a human.
- `DRY_RUN` retires: `po_manager` now really posts POs to the world, because the approvals
  queue + spend cap are the actual safeguards, and the world is a simulation.

---

## 6. Decision log

**Research question:** How do we separate an autonomous agent from its environment so the
agent is transferable to a real deployment while remaining demonstrable in simulation?

**LO stage:** Designing → Realizing

**Decision 1 — Two services, not two packages.**
Chosen: standalone world FastAPI on :8001 with its own DB; Betsy on :8000 reaches it only
through `WorldClient`. Rejected: single process with a `/sim`-mounted sub-app (weaker
boundary, no process-level proof the agent works over the wire; ERP swap less credible).
Cost accepted: two processes to run (`run_all.py` mitigates).

**Decision 2 — Orchestra becomes the production agent.**
Chosen: the multi-agent fan-out graph, because a living world produces concurrent,
heterogeneous findings (stockouts + invoices + outages in the same day) which is what the
parallel analysts + orchestrator conflict resolution were built for. Rejected: keeping the
linear pipeline as default (simpler but serializes unrelated concerns). Pipeline is kept
as a DL-04 comparison artifact.

**Decision 3 — Learned scores move into Betsy's DB.**
Chosen: world exposes only objective delivery facts; Betsy computes and persists EMA in
betsy.db. Rejected: world-maintained `reliability_score` (as in the POC) — that makes the
environment carry agent memory, breaks the ERP analogy, and was the root cause of the
learning-wiped-on-restart bug. Side effect: the world keeps a hidden `true_reliability`
for jitter generation, giving us a clean "ground truth vs learned belief" evaluation axis.

**Decision 4 — Deterministic tick RNG keyed by (seed, day).**
Chosen: `random.Random(f"{seed}:{day}")` per tick. Rejected: one long-lived RNG stream
(not restart-safe without persisting generator state) and true randomness (untestable).

**Success criteria / validation:**
- ✅ Agent runs the full lifecycle with no human trigger (detect → order → deliver →
  reconcile → learn) — validated by an end-to-end sim test stepping ~20 days.
- ✅ Learning survives restarts of either service.
- ✅ Same seed + same steps ⇒ byte-identical world state (determinism test).
- ✅ `true_reliability` never appears in any API payload (contract test).

**What it unlocks:** evaluation of learned scores against ground truth; multiple
world instances (different seeds) for comparative agent runs; a credible story for
pointing Betsy at a real ERP by re-implementing `WorldClient` only.

---

## 7. Component map (implementation)

| Piece | Path |
|---|---|
| World config / DB / seeding | `world/config.py`, `world/db.py` |
| Tick engine + runner | `world/engine.py`, `world/runner.py` |
| World routers | `world/routers/{inventory,suppliers,orders,invoices,clock,events,snapshot,admin}.py` |
| Event scripts | `world/scenarios/*.json` |
| Adapter | `shared/world_client.py` |
| Agent memory (EMA) | `server/memory.py` + betsy.db tables |
| Agent trigger loop | `server/agent_loop.py` |
| Betsy proxies to world | `server/routers/{inventory,suppliers,orders,invoices,sim}.py` |
| Entrypoints | `run_world.py`, `run_server.py`, `run_all.py` |

Retired: `server/state.py`, `server/routers/scenarios.py`, root `scenarios/`,
`pending_approval` PO status, `DRY_RUN` flags, scheduler pipeline auto-run.
