# Test Report — DL-05 HITL Approval Queue
**Branch:** feat/dl05-approvals  
**Date:** 2026-05-31  
**Tester:** automated via curl against live server (uvicorn, port 8000)

---

## What was tested

The full approve/decline loop introduced in DL-05:
- `GET /api/approvals` returns pending items
- Pipeline queues `requires_human=True` decisions to `/api/approvals`
- `POST /api/approvals/{id}/approve` creates the PO and logs `human_approved`
- `POST /api/approvals/{id}/reject` logs `human_rejected`, no action taken
- Guard rails: double-resolve and unknown-id are rejected cleanly

---

## Bug found during testing

**Root cause:** `state.reset()` included `self.approvals = []`, which was added when wiring up the reset flow. The pipeline calls `api.reset_scenario()` at the end of every run — so approvals were being queued and then immediately wiped.

**Fix:** Removed `self.approvals = []` from `reset()`. Approvals are user-facing decisions that live until Jenny acts on them — they are independent of scenario state. Committed separately: `fix: don't clear approvals on scenario reset`.

---

## Test results

| # | Test | Expected | Result | Pass |
|---|------|----------|--------|------|
| T1 | `GET /api/approvals` before any run | `[]` | `[]` | ✅ |
| T2 | Trigger `stockout_warning` pipeline via `/api/run-agent` | `{"status":"started"}` | `{"status":"started","mode":"pipeline","scenario":"stockout_warning"}` | ✅ |
| T3 | `GET /api/approvals` after run | 2 pending items (generate_po + flag_duplicate) | 2 items — `flag_duplicate` SKU-004 (confidence 0.7), `generate_po` SKU-003 €11,325 (confidence 1.0) | ✅ |
| T4 | `POST /api/approvals/{id}/reject` on duplicate flag | `{"status":"rejected"}` | `{"status":"rejected"}` | ✅ |
| T5 | `POST /api/approvals/{id}/approve` on generate_po | `{"status":"approved","po_id":"..."}` | `{"status":"approved","po_id":"PO-20260531-0E74"}` | ✅ |
| T6 | `GET /api/approvals` after both resolved | `[]` | `[]` | ✅ |
| T7 | PO `PO-20260531-0E74` in `/api/purchase-orders` | `requested_by: betsy-human-approved` | Present with correct fields, `status: approved` | ✅ |
| T8 | Agent log contains `human_approved` and `human_rejected` entries | 2 entries with correct metadata | Both entries present, metadata includes `decision_id` and `po_id` | ✅ |
| T9 | Re-approve an already-resolved item | `400` | `400` | ✅ |
| T10 | Approve non-existent `decision_id` | `404` | `404` | ✅ |
| T11 | `duplicate_invoice` scenario queues flag items | `flag_duplicate` items pending | 3 × `flag_duplicate` SKU-004 queued | ✅ |

**11/11 passed.**

---

## Observations

**PO created correctly:** The approved PO was created with `requested_by: betsy-human-approved`, distinguishing human-approved orders from auto-approved ones in the purchase orders list.

**Agent log records the human decision:** Both `human_approved` and `human_rejected` entries appear in the agent log with the `decision_id`, making it auditable — you can trace every approval action back to the queued decision.

**Financial safeguard held:** The stockout_warning PO total was €11,325 (above the €5,000 auto-approve limit). The agent correctly stopped and queued it. The human approved it and the PO was created — so the safeguard is blocking auto-action but not blocking human action. That's the intended behaviour.

**T11 note:** The `duplicate_invoice` scenario produced 3 pending `flag_duplicate` items for SKU-004. This is expected — the scenario injects multiple duplicate invoice pairs and the detect node finds each one independently. Not a bug.

---

## What this enables

- Jenny can now open betsy.html, see approval cards, and click "Yes, go ahead" or "Skip this"
- Approving a `generate_po` creates the PO in real-time — visible in index.html orders tab immediately
- Every approval/rejection is recorded in the agent log with full traceability
- The betsy.html decision log section shows `✅ You approved` / `❌ You declined` entries after acting
