"""
DL-06 evidence script — EMA learning in the live two-service setup.

Requires both services running:
  python run_world.py
  python run_server.py

Usage:
  python tests/test_ema_learning.py

What it does:
  1. Resets the world and pauses the clock.
  2. Reads Betsy's learned scores (bootstrapped from seeded delivery history).
  3. Places a PO, steps the sim until it delivers, waits for Betsy's agent
     loop to observe it, and asserts the EMA moved by exactly
     alpha * performance + (1 - alpha) * old.
"""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

BETSY = "http://localhost:8000"
ALPHA = 0.2


def ema_expected(old: float, performance: float) -> float:
    return round(min(1.0, max(0.0, ALPHA * performance + (1 - ALPHA) * old)), 4)


def get_scores() -> dict:
    return httpx.get(f"{BETSY}/api/suppliers/scores", timeout=10).json()


def wait_for_observation(po_id: str, timeout_s: int = 30) -> dict | None:
    """Poll the agent log until the EMA update for this PO appears."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        log = httpx.get(f"{BETSY}/api/agent-log", timeout=10).json()
        for entry in reversed(log):
            if (entry.get("trigger") == "ema_score_update"
                    and entry.get("metadata", {}).get("po_id") == po_id):
                return entry
        time.sleep(2)
    return None


def main() -> int:
    print("=" * 60)
    print("EMA LEARNING EVIDENCE — two-service architecture")
    print("=" * 60)

    try:
        health = httpx.get(f"{BETSY}/health", timeout=3).json()
    except Exception:
        print("ERROR: Betsy not reachable. Start both services first.")
        return 1
    if not health.get("world_up", True):
        print("ERROR: world service not reachable from Betsy.")
        return 1

    print("\n[1] Reset world, pause clock")
    httpx.post(f"{BETSY}/api/sim/reset", timeout=30)
    httpx.post(f"{BETSY}/api/sim/clock/pause", timeout=10)

    print("[2] Waiting for Betsy to bootstrap scores from seeded history...")
    time.sleep(6)  # one or two agent-loop polls
    before = get_scores()
    print(f"    Learned scores for {len(before)} suppliers")
    for sid, s in sorted(before.items()):
        print(f"      {sid}: {s['reliability_score']:.4f} ({s['deliveries_observed']} deliveries)")

    supplier = "SUP-001"

    print(f"\n[3] Placing PO with {supplier} (lead 2 days), stepping sim until delivery")
    po = httpx.post(f"{BETSY}/api/purchase-orders", json={
        "supplier_id": supplier, "sku_id": "SKU-003",
        "quantity": 100, "unit_price": 12.50,
        "reason": "EMA evidence test", "requested_by": "test-script",
    }, timeout=10).json()
    print(f"    {po['po_id']} expected {po['expected_delivery']}")

    delivered = None
    for _ in range(12):
        httpx.post(f"{BETSY}/api/sim/clock/step", params={"days": 1}, timeout=60)
        orders = httpx.get(f"{BETSY}/api/purchase-orders", timeout=10).json()
        state = next(o for o in orders if o["po_id"] == po["po_id"])
        if state["status"] == "delivered":
            delivered = state
            break
    if not delivered:
        print("ERROR: PO not delivered within 12 sim days")
        return 1
    print(f"    Delivered {delivered['actual_delivery']}")

    print("[4] Waiting for Betsy's agent loop to observe the delivery...")
    entry = wait_for_observation(po["po_id"])
    if not entry:
        print("ERROR: no ema_score_update log entry appeared (is the agent loop running?)")
        return 1

    meta = entry["metadata"]
    lateness = meta["lateness_days"]
    performance = max(0.0, 1.0 - lateness * 0.1)
    expected = ema_expected(meta["old_score"], performance)
    actual = meta["new_score"]
    print(f"    lateness={lateness}d performance={performance:.2f}")
    print(f"    score {meta['old_score']:.4f} -> {actual:.4f} (expected {expected:.4f})")

    ok = abs(actual - expected) < 1e-6
    print("\n" + ("PASS: EMA math verified against live delivery" if ok else "FAIL: EMA mismatch"))
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
