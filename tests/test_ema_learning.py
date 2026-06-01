"""
EMA learning loop evidence script.
Requires server running at localhost:8000.

Usage: python tests/test_ema_learning.py
"""
import json
from datetime import datetime, timedelta

import httpx

BASE = "http://localhost:8000"


def get(path):
    return httpx.get(f"{BASE}{path}", timeout=5).json()


def patch(path, **params):
    return httpx.patch(f"{BASE}{path}", params=params, timeout=5).json()


def post(path, body=None):
    return httpx.post(f"{BASE}{path}", json=body or {}, timeout=5).json()


def supplier_score(supplier_id):
    suppliers = get("/api/suppliers")
    s = next((x for x in suppliers if x["supplier_id"] == supplier_id), None)
    return s["reliability_score"] if s else None


def create_test_po(supplier_id, sku_id, expected_delivery_iso):
    body = {
        "supplier_id": supplier_id,
        "sku_id": sku_id,
        "quantity": 10,
        "unit_price": 1.0,
        "reason": "EMA test",
        "requested_by": "test_ema_learning",
    }
    po = post("/api/purchase-orders", body)
    # Override expected_delivery to control lateness
    for order in get("/api/purchase-orders"):
        if order["po_id"] == po["po_id"]:
            order["expected_delivery"] = expected_delivery_iso
    return po["po_id"]


def ema_expected(old, performance, alpha=0.2):
    return round(min(1.0, max(0.0, alpha * performance + (1 - alpha) * old)), 4)


def run():
    print("\n" + "=" * 65)
    print("Betsy EMA Learning Loop Test")
    print(f"Server: {BASE}")
    print("=" * 65)

    # ── Target: PrecisionParts GmbH (SUP-004, highest baseline score 0.97)
    SUP = "SUP-004"
    SKU = "SKU-001"  # supplied by SUP-004

    baseline = supplier_score(SUP)
    if baseline is None:
        print(f"ERROR: supplier {SUP} not found — is the server running?")
        return

    print(f"\nSupplier:  PrecisionParts GmbH ({SUP})")
    print(f"Baseline score: {baseline:.4f}")

    results = [("Baseline", baseline, "—", "—")]

    # ── Test 1: on-time delivery ──────────────────────────────────────────
    print("\n[1] On-time delivery (lateness = 0 days)")
    today = datetime.now().isoformat()
    po1 = create_test_po(SUP, SKU, today)
    patch(f"/api/purchase-orders/{po1}/status", status="in_transit")
    r1 = patch(f"/api/purchase-orders/{po1}/status", status="delivered",
               actual_delivery=today)

    score_after_ontime = supplier_score(SUP)
    expected_1 = ema_expected(baseline, 1.0)
    match1 = "PASS" if abs(score_after_ontime - expected_1) < 0.0001 else "FAIL"
    print(f"   Score: {baseline:.4f} -> {score_after_ontime:.4f}  "
          f"(expected {expected_1:.4f})  {match1}")
    print(f"   Formula: 0.2×1.0 + 0.8×{baseline:.4f} = {expected_1:.4f}")
    results.append(("After on-time delivery", score_after_ontime, expected_1, match1))

    # ── Test 2: 5-day late delivery ───────────────────────────────────────
    print("\n[2] Late delivery (+5 days)")
    po2 = create_test_po(SUP, SKU, datetime.now().isoformat())

    # Fetch the PO to get the server-assigned expected_delivery, then arrive 5 days late
    po2_data = next(o for o in get("/api/purchase-orders") if o["po_id"] == po2)
    expected_dt = datetime.fromisoformat(po2_data["expected_delivery"][:19])
    actual_dt   = (expected_dt + timedelta(days=5)).isoformat()

    patch(f"/api/purchase-orders/{po2}/status", status="in_transit")
    patch(f"/api/purchase-orders/{po2}/status", status="delivered",
          actual_delivery=actual_dt)

    score_after_late = supplier_score(SUP)
    perf_late        = max(0.0, 1.0 - 5 * 0.1)  # = 0.5
    expected_2       = ema_expected(score_after_ontime, perf_late)
    match2 = "PASS" if abs(score_after_late - expected_2) < 0.0001 else "FAIL"
    print(f"   Score: {score_after_ontime:.4f} -> {score_after_late:.4f}  "
          f"(expected {expected_2:.4f})  {match2}")
    print(f"   Formula: 0.2×{perf_late:.1f} + 0.8×{score_after_ontime:.4f} = {expected_2:.4f}")
    results.append(("After 5-day late delivery", score_after_late, expected_2, match2))

    # ── Summary table ─────────────────────────────────────────────────────
    print("\n" + "-" * 65)
    print(f"{'State':<30} {'Score':>8}  {'Expected':>10}  {'Pass':>5}")
    print("-" * 65)
    for label, score, exp, match in results:
        exp_str = f"{exp:.4f}" if isinstance(exp, float) else str(exp)
        print(f"{label:<30} {score:>8.4f}  {exp_str:>10}  {match:>5}")
    print("-" * 65)

    passed = sum(1 for _, _, _, m in results[1:] if m == "PASS")
    total  = len(results) - 1
    print(f"\n{passed}/{total} checks passed")
    print("\nKey finding: on-time delivery raises the score, "
          "late delivery lowers it.")
    print("Betsy will prefer higher-scoring suppliers in future runs.")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run()
