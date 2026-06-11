# Test Report — DL-05 Human-in-the-Loop Approval Queue

**Branch:** feat/dl05-approvals
**Date:** 2026-05-31
**How it was tested:** automated calls against the live server (running on port 8000)

---

## What was tested

This report checks the full approve-and-decline loop built in DL-05 — the path that turns a decision Betsy cannot make on its own into something Jenny can act on. In plain terms, the test confirms four things: that the pipeline puts a held decision into the approval queue, that approving it creates a real purchase order, that declining it records the choice and does nothing else, and that bad requests (acting on the same item twice, or on an item that does not exist) are turned away cleanly.

---

## The bug found during testing

At first the queue came up empty straight after a pipeline run, even though the queuing code was correct. The cause was the reset() function: it was clearing the approval queue at the end of every run, because clearing was added by mistake when the scenario-reset flow was wired up. The pipeline resets the scenario after each run, so every approval was being queued and then wiped a moment later.

The fix was to stop reset() from touching the approvals. Approvals are not scenario data that should be wiped between runs — they are Jenny's pending decisions, and they need to live until she acts on them. Removing that one line fixed it, and it was committed on its own so the change is easy to trace.

---

## Test results

All eleven checks passed.

| # | Test | Expected | Result | Pass |
|---|------|----------|--------|------|
| T1 | List approvals before any run | empty | empty | pass |
| T2 | Trigger the stockout run | run starts | run started in pipeline mode | pass |
| T3 | List approvals after the run | 2 pending items | flag-duplicate for SKU-004, generate-PO for SKU-003 at €11,325 | pass |
| T4 | Decline the duplicate-invoice flag | recorded as rejected | recorded as rejected | pass |
| T5 | Approve the generate-PO item | a new PO id returned | PO-20260531-0E74 created | pass |
| T6 | List approvals after both are resolved | empty | empty | pass |
| T7 | Find that PO in the orders list | marked betsy-human-approved | present, status approved | pass |
| T8 | Agent log has the human decisions | approved + declined entries | both present, with the decision id and PO id | pass |
| T9 | Approve an already-resolved item | refused (400) | refused (400) | pass |
| T10 | Approve an unknown id | refused (404) | refused (404) | pass |
| T11 | Duplicate-invoice scenario queues flags | flag items pending | 3 duplicate flags queued for SKU-004 | pass |

---

## What the results show

The approved purchase order was created and marked betsy-human-approved, which keeps human-approved orders separate from ones Betsy placed on its own. Both the approve and the decline were written to the agent log with the decision id, so every human action can be traced back to the exact decision it resolved.

The financial safeguard held. The stockout order came to €11,325, above the €5,000 limit for autonomous spending, so Betsy stopped and queued it rather than placing it. Jenny then approved it and the order went through. That is the behaviour we want: the limit blocks Betsy from acting alone on a large order, but it does not block a person from approving it.

The last check (T11) produced three pending duplicate flags rather than one. That is expected, not a fault — the duplicate-invoice scenario seeds several matching invoice pairs, and the detect step finds each one on its own.

---

## What this enables

After DL-05, Jenny can open Betsy's page, see the pending approval cards, and choose "Yes, go ahead" or "Skip this". Approving a held order creates the purchase order straight away, visible in the orders view in real time. Every approval and decline is recorded in the agent log with a full trail, and the decision-log section of the page shows what she approved or declined after she acts.
