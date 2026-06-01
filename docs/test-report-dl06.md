# Test Report — DL-06 Persistence, EMA Learning, APScheduler, Stats
**Branch:** feat/dl06-persistence-learning  
**Date:** 2026-05-31  
**Tester:** automated via PowerShell + curl against live server (uvicorn, port 8000)

---

## What was tested

All four DL-06 pillars:
1. **SQLite persistence** — agent_log and approvals survive server restarts
2. **EMA supplier score updates** — on-time delivery raises score, late delivery lowers it
3. **APScheduler** — scheduler starts with server, next_run visible in /api/stats
4. **Stats endpoint + betsy.html panel** — correct shape and values

---

## Test results

| # | Test | Expected | Result | Pass |
|---|------|----------|--------|------|
| T1 | Server health + scheduler active | `scheduler_active: true`, `next_run` set | Both present | ✅ |
| T2 | POST to `/api/agent-log` writes to SQLite | Row appears in `betsy.db` `agent_log` table | `id=7, trigger=test_persistence, decision=test_entry` | ✅ |
| T3 | POST to `/api/approvals` writes to SQLite | Row appears in `betsy.db` `approvals` table | `decision_id=test-dl06-persist-001, status=pending` | ✅ |
| T4 | Server restart — log + approvals reload from DB | 7 log entries + 1 pending approval present after restart | `7 entries reloaded`, `1 pending approval survived restart` | ✅ |
| T5a | EMA — on-time delivery raises score | `0.2×1.0 + 0.8×0.97 = 0.976` | Score `0.9700 → 0.9760` — matches formula | ✅ |
| T5b | EMA — 5-day late delivery lowers score | `0.2×0.5 + 0.8×0.976 = 0.8808` | Score `0.9760 → 0.8808` — matches formula | ✅ |
| T6 | `GET /api/stats` returns correct shape | All fields present, scheduler info populated | `decisions_total=9`, `scheduler_active=True`, `next_run` set, `queue_value_eur=5500.0` | ✅ |
| T7 | Approve queued item — DB row updated | `status=approved`, `resolved_at` set, queue empties | `status=approved, resolved_at=2026-05-31`, `pending_approvals=0` | ✅ |
| T8 | Double-resolve guard | `400` | `HTTP 400` | ✅ |

**9/9 passed (including 2/2 EMA formula checks).**

---

## EMA formula verification

Supplier: PrecisionParts GmbH (SUP-004), baseline score 0.97.

| Event | Lateness | Performance | Formula | Before | After | Match |
|-------|----------|-------------|---------|--------|-------|-------|
| On-time delivery | 0 days | 1.0 | `0.2×1.0 + 0.8×0.9700` | 0.9700 | **0.9760** | ✅ |
| 5-day late delivery | 5 days | 0.5 | `0.2×0.5 + 0.8×0.9760` | 0.9760 | **0.8808** | ✅ |

Performance decay: `max(0, 1.0 - lateness × 0.1)` — 10 days late = 0.0 performance.

---

## Persistence verified

State before restart:
- 7 agent_log entries (including EMA score_updated events and test_persistence entry)
- 1 pending approval (`test-dl06-persist-001`, `generate_po`, €5,500)

State after server restart — reloaded from `betsy.db`:
- 7 agent_log entries ✅
- 1 pending approval ✅

No data lost. `betsy.db` is created at project root on first server start.

---

## APScheduler confirmed

- `scheduler_active: true` visible in `/api/stats` immediately after server start
- `next_run` field shows ISO timestamp of the next scheduled pipeline run
- Default interval: 30 minutes (override with `AGENT_INTERVAL_MINUTES` env var)
- Set `AGENT_INTERVAL_MINUTES=1` for testing — auto-run fires within 60s

---

## Stats panel (betsy.html)

`GET /api/stats` returns:
```json
{
  "decisions_total": 9,
  "decisions_auto": 0,
  "decisions_human": 0,
  "ema_updates": 6,
  "auto_rate_pct": 0.0,
  "pending_approvals": 1,
  "queue_value_eur": 5500.0,
  "last_run": null,
  "scheduler_active": true,
  "next_run": "2026-05-31T18:44:57..."
}
```

betsy.html stats panel (5 cards): decisions made · autonomous rate · awaiting your OK · value in queue · next auto-run. Updates every 5 seconds with the rest of the dashboard.

---

## Known limitations (documented in DL-06)

- **Supplier scores are session-persistent only** — EMA updates apply to in-memory state loaded from `mock_data/suppliers.json`. A server restart reloads baseline scores. Score learning is demonstrated within a session; persisting scores to the DB is a future step.
- **Concurrent runs** — if a scheduled run and a manual run overlap, both can enqueue approvals simultaneously. No locking between pipeline threads.
- **Score drift on scenario reset** — `state.reset()` reloads suppliers from the original JSON, undoing any EMA changes made during the session. Don't mix EMA tests with scenario injection in the same flow.
