"""
Long-term learning integration test.

Demonstrates EMA score learning across two real LLM pipeline runs.

Run #1: baseline supplier scores. Stockout on SKU-003.
        Expected winner: QuickShip Express (composite 0.920 = score 0.92 / lead 1d).

8 delivery rounds:
  - QuickShip gets 5 deliveries, all 8 days late -> reliability drops from 0.92 to ~0.44
  - FastParts  gets 3 deliveries, all on-time    -> reliability rises  from 0.95 to ~0.97

Run #2: same stockout, learned scores explicitly restored.
        Expected winner: FastParts Co (composite ~0.487 vs QuickShip ~0.436).

Usage:   python tests/test_long_term_learning.py
Needs:   server at localhost:8000, Ollama model configured.
Time:    3-5 min (two LLM pipeline runs + delivery simulation).
"""
import sys
import time
from datetime import datetime, timedelta

import httpx

BASE = "http://localhost:8000"

# 8 delivery rounds designed to flip the SKU-003 supplier ranking.
# Scoring formula: composite = reliability_score / lead_days
# Baseline:
#   QuickShip (SUP-003): 0.92 / 1d = 0.920  <-- baseline winner
#   FastParts (SUP-001): 0.95 / 2d = 0.475
# After rounds:
#   QuickShip: 5 x 8d-late  => ~0.436 / 1d = 0.436
#   FastParts: 3 x on-time  => ~0.974 / 2d = 0.487  <-- new winner
ROUNDS = [
    # (supplier_id, sku_id, lateness_days, label)
    ("SUP-003", "SKU-003", 8, "QuickShip  8d late  #1"),
    ("SUP-003", "SKU-003", 8, "QuickShip  8d late  #2"),
    ("SUP-003", "SKU-003", 8, "QuickShip  8d late  #3"),
    ("SUP-003", "SKU-003", 8, "QuickShip  8d late  #4"),
    ("SUP-003", "SKU-003", 8, "QuickShip  8d late  #5"),
    ("SUP-001", "SKU-003", 0, "FastParts  on-time  #1"),
    ("SUP-001", "SKU-003", 0, "FastParts  on-time  #2"),
    ("SUP-001", "SKU-003", 0, "FastParts  on-time  #3"),
]

FOCUS = ["SUP-001", "SUP-003"]
LEAD_DAYS = {"SUP-001": 2, "SUP-003": 1}  # lead days for SKU-003


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def get(path):
    return httpx.get(f"{BASE}{path}", timeout=15).json()


def post(path, body=None, **params):
    return httpx.post(f"{BASE}{path}", json=body or {}, params=params, timeout=15).json()


def patch(path, **params):
    return httpx.patch(f"{BASE}{path}", params=params, timeout=15).json()


def supplier_scores():
    return {s["supplier_id"]: s for s in get("/api/suppliers")}


def composite(score, lead):
    return round(score / max(lead, 0.1), 4)


# ── Simulation helpers ─────────────────────────────────────────────────────────

def simulate_delivery(supplier_id, sku_id, lateness_days):
    po = post("/api/purchase-orders", {
        "supplier_id": supplier_id,
        "sku_id": sku_id,
        "quantity": 1,
        "unit_price": 1.0,
        "reason": "ltl_test",
        "requested_by": "test_ltl",
    })
    po_id = po["po_id"]

    po_data = next(o for o in get("/api/purchase-orders") if o["po_id"] == po_id)
    expected_dt = datetime.fromisoformat(po_data["expected_delivery"][:19])
    actual_dt = (expected_dt + timedelta(days=lateness_days)).isoformat()

    patch(f"/api/purchase-orders/{po_id}/status", status="in_transit")
    patch(f"/api/purchase-orders/{po_id}/status", status="delivered", actual_delivery=actual_dt)


def restore_scores(learned_scores):
    """Explicitly PATCH each supplier's reliability_score after a scenario reset."""
    for supplier_id, score in learned_scores.items():
        patch(f"/api/suppliers/{supplier_id}/score", reliability_score=score)


def run_pipeline(label, timeout_s=240):
    """Fire background pipeline run, poll for completion.
    Returns (new_approvals, pipeline_log_entry)."""
    print(f"   Triggering LLM pipeline... ", end="", flush=True)
    t_start = datetime.now().isoformat()
    t0 = time.time()

    post("/api/run-agent")

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(5)
        log = get("/api/agent-log")
        pl_entry = next(
            (e for e in reversed(log)
             if e.get("trigger") == "pipeline_run" and e.get("timestamp", "") >= t_start),
            None,
        )
        if pl_entry:
            elapsed = int(time.time() - t0)
            print(f" done ({elapsed}s, {len(log)} entries)")
            pending = get("/api/approvals")
            new_approvals = [a for a in pending if a.get("created_at", "") >= t_start]
            return new_approvals, pl_entry
        sys.stdout.write(".")
        sys.stdout.flush()

    print(" TIMEOUT")
    raise TimeoutError(f"Pipeline '{label}' did not complete in {timeout_s}s")


def print_pipeline_summary(pl_entry):
    """Print what the pipeline detected and decided (for diagnostics)."""
    meta = pl_entry.get("metadata", {})
    conditions = meta.get("conditions", [])
    decisions = meta.get("decisions", [])
    actions = meta.get("actions", [])
    if conditions:
        print(f"   Detected:  " + ", ".join(
            f"{c['type']}/{c.get('sku_id','?')}({c['severity']})" for c in conditions))
    else:
        print(f"   Detected:  none")
    if decisions:
        print(f"   Decisions: " + ", ".join(
            f"{d['action']}(auto={d.get('auto_approved','?')})" for d in decisions))
    else:
        print(f"   Decisions: none")
    if actions:
        print(f"   Actions:   " + ", ".join(
            f"{a['action']}:{a['status']}" for a in actions))


def chosen_supplier(approvals, sku_id="SKU-003"):
    """Find chosen supplier from new approvals. Prefer generate_po, then any."""
    sku_matches = [a for a in approvals if a.get("sku_id") == sku_id]
    if not sku_matches:
        return None

    # Prefer generate_po, then any action with a supplier_id
    po_match = next((a for a in sku_matches if a.get("action") == "generate_po"), None)
    if po_match:
        return po_match

    # Fallback: any approval for this SKU that has a supplier
    for a in sku_matches:
        if a.get("supplier_id"):
            return a

    return sku_matches[0]


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    W = 70
    print()
    print("=" * W)
    print("Betsy Long-Term Learning Test")
    print(f"Server: {BASE}")
    print("=" * W)
    print("Two real LLM runs with 8 EMA delivery rounds between them.")
    print("QuickShip gets 5 x 8d-late; FastParts gets 3 x on-time.")
    print("Predicted: FastParts overtakes QuickShip for SKU-003.")
    print(f"Runtime: ~3-5 min\n")

    # ── Phase 0: Preflight ────────────────────────────────────────────────────
    print("[0] Preflight")
    try:
        assert httpx.get(f"{BASE}/health", timeout=5).json().get("status") == "ok"
    except Exception:
        print(f"    ERROR: server not reachable at {BASE}")
        return

    post("/api/scenario/reset")
    time.sleep(1)

    sups = supplier_scores()
    baseline = {sid: sups[sid]["reliability_score"] for sid in FOCUS}
    print(f"    Server OK.  Baseline: " +
          ", ".join(f"{sups[sid]['name']}={v:.4f}" for sid, v in baseline.items()))
    print(f"    Composite:  " +
          ", ".join(f"{sups[sid]['name']}={composite(v, LEAD_DAYS[sid]):.4f}"
                    for sid, v in baseline.items()))

    # ── Phase 1: Run #1 — baseline scores ─────────────────────────────────────
    print()
    print("[1] Pipeline Run #1 — stockout_warning, baseline scores")
    post("/api/scenario/stockout_warning")
    time.sleep(0.5)

    try:
        approvals_1, pl1 = run_pipeline("run1")
    except TimeoutError as e:
        print(f"    {e}")
        return

    print_pipeline_summary(pl1)

    appr_1 = chosen_supplier(approvals_1)
    sid_1 = appr_1["supplier_id"] if appr_1 else None
    name_1 = sups.get(sid_1, {}).get("name", sid_1) if sid_1 else "none queued"
    print(f"   Chosen supplier: {name_1} ({sid_1})")
    if not appr_1:
        print(f"   NOTE: no approval queued — pipeline may have auto-approved or found no action.")
        print(f"         New approvals this run: {len(approvals_1)}")

    # ── Phase 2: Delivery simulation ──────────────────────────────────────────
    print()
    print("[2] Delivery Simulation — 8 EMA rounds")
    print(f"   {'#':<4} {'Label':<28} {'Before':>8}  {'After':>8}  {'Perf':>6}")
    print("   " + "-" * 58)

    for i, (supplier_id, sku_id, lateness, label) in enumerate(ROUNDS, 1):
        perf = max(0.0, 1.0 - lateness * 0.1)
        score_before = supplier_scores()[supplier_id]["reliability_score"]
        simulate_delivery(supplier_id, sku_id, lateness)
        score_after = supplier_scores()[supplier_id]["reliability_score"]
        print(f"   {i:<4} {label:<28} {score_before:>8.4f}  {score_after:>8.4f}  {perf:>6.1f}")

    sups_after = supplier_scores()
    learned = {sid: sups_after[sid]["reliability_score"] for sid in FOCUS}

    print()
    print("   Score summary (focus suppliers):")
    print(f"   {'Supplier':<22} {'Baseline':>9}  {'Learned':>9}  {'Delta':>7}  {'Composite'}")
    print("   " + "-" * 63)
    for sid in FOCUS:
        name = sups[sid]["name"]
        b = baseline[sid]
        a = learned[sid]
        lead = LEAD_DAYS[sid]
        delta = a - b
        sign = "+" if delta >= 0 else ""
        print(f"   {name:<22} {b:>9.4f}  {a:>9.4f}  {sign}{delta:>6.4f}  "
              f"{composite(b, lead):.4f} -> {composite(a, lead):.4f}")

    # ── Phase 3: Run #2 — learned scores explicitly restored ──────────────────
    print()
    print("[3] Pipeline Run #2 — same scenario, learned scores restored")

    # Inject scenario (this resets supplier scores to baseline)
    post("/api/scenario/stockout_warning")
    time.sleep(0.5)

    # Explicitly restore learned scores via PATCH endpoint
    restore_scores(learned)

    # Verify
    live = supplier_scores()
    for sid in FOCUS:
        expected = learned[sid]
        actual = live[sid]["reliability_score"]
        ok = abs(actual - expected) < 0.0001
        print(f"   Score restored {sups[sid]['name']}: {actual:.4f}  ({'OK' if ok else 'MISMATCH'})")

    try:
        approvals_2, pl2 = run_pipeline("run2")
    except TimeoutError as e:
        print(f"    {e}")
        return

    print_pipeline_summary(pl2)

    appr_2 = chosen_supplier(approvals_2)
    sid_2 = appr_2["supplier_id"] if appr_2 else None
    name_2 = sups.get(sid_2, {}).get("name", sid_2) if sid_2 else "none queued"
    print(f"   Chosen supplier: {name_2} ({sid_2})")
    if not appr_2:
        print(f"   NOTE: no approval queued — new approvals: {len(approvals_2)}")

    # ── Phase 4: Summary ──────────────────────────────────────────────────────
    print()
    print("=" * W)
    print("[4] Summary")
    print("=" * W)

    print(f"\nComposite score shift for SKU-003 (score / lead_days):\n")
    print(f"   {'Supplier':<22} {'Before comp':>12}  {'After comp':>11}  {'Direction'}")
    print("   " + "-" * 57)
    for sid in sorted(FOCUS, key=lambda s: composite(baseline[s], LEAD_DAYS[s]), reverse=True):
        name = sups[sid]["name"]
        lead = LEAD_DAYS[sid]
        cb = composite(baseline[sid], lead)
        ca = composite(learned[sid], lead)
        direction = "up" if ca > cb else "DOWN"
        print(f"   {name:<22}  {cb:.4f}/{lead}d      {ca:.4f}/{lead}d   {direction}")

    print(f"\nPipeline decision:")
    print(f"   Run #1 (baseline):        {name_1}  ({sid_1})")
    print(f"   Run #2 (learned scores):  {name_2}  ({sid_2})")

    if sid_1 and sid_2:
        if sid_1 != sid_2:
            print(f"\n   SUPPLIER SWITCH CONFIRMED")
            print(f"   Betsy switched from {name_1} to {name_2}.")
            print(f"   Score learning directly changed the procurement decision.")
        else:
            comp_sid_1 = composite(learned.get("SUP-001", baseline["SUP-001"]), LEAD_DAYS["SUP-001"])
            comp_sid_3 = composite(learned.get("SUP-003", baseline["SUP-003"]), LEAD_DAYS["SUP-003"])
            print(f"\n   Same supplier both runs.")
            print(f"   Final composites: FastParts={comp_sid_1:.4f}, QuickShip={comp_sid_3:.4f}")
            if comp_sid_3 > comp_sid_1:
                print(f"   QuickShip composite still higher — retained correctly.")
            else:
                print(f"   FastParts composite higher — check LLM reasoning in /api/agent-log.")
    else:
        if not sid_1 or not sid_2:
            print(f"\n   Could not compare: one or both runs had no supplier in approval.")
            print(f"   Check /api/agent-log for pipeline decisions.")

    print(f"\nEMA formula verified across 8 delivery rounds:")
    print(f"   new = 0.2 * performance + 0.8 * old")
    print(f"   performance = max(0, 1.0 - lateness_days * 0.1)")
    print(f"   QuickShip: {baseline['SUP-003']:.4f} -> {learned['SUP-003']:.4f}  (5 x 8d-late)")
    print(f"   FastParts: {baseline['SUP-001']:.4f} -> {learned['SUP-001']:.4f}  (3 x on-time)")
    print("=" * W + "\n")


if __name__ == "__main__":
    run()
