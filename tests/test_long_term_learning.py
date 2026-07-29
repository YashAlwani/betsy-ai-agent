"""
Long-term learning evidence script — two-service architecture.

Demonstrates that Betsy's learned supplier ranking for SKU-003 flips after
observing real delivery outcomes:

  Baseline (bootstrapped from seeded history):
    QuickShip (SUP-003, lead 1d) wins on composite = score / lead_days.
  8 forced delivery rounds:
    - QuickShip: 5 deliveries, all 8 days late  -> score collapses
    - FastParts: 3 deliveries, all on time      -> score climbs
  After observation:
    FastParts (SUP-001, lead 2d) becomes the recommended supplier.

Usage:   python tests/test_long_term_learning.py
Needs:   both services running (python run_world.py + python run_server.py).
Time:    ~1 min. No LLM required (ranking uses the same composite formula
         as orchestra's supplier matrix: reliability_score / lead_days).
"""
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

BETSY = "http://localhost:8000"
WORLD = "http://localhost:8001"

ROUNDS = [
    # (supplier_id, lateness_days, label)
    ("SUP-003", 8, "QuickShip  8d late  #1"),
    ("SUP-003", 8, "QuickShip  8d late  #2"),
    ("SUP-003", 8, "QuickShip  8d late  #3"),
    ("SUP-003", 8, "QuickShip  8d late  #4"),
    ("SUP-003", 8, "QuickShip  8d late  #5"),
    ("SUP-001", 0, "FastParts  on-time  #1"),
    ("SUP-001", 0, "FastParts  on-time  #2"),
    ("SUP-001", 0, "FastParts  on-time  #3"),
]
FOCUS = {"SUP-001": "FastParts", "SUP-003": "QuickShip"}
SKU = "SKU-003"


def get(path, base=BETSY):
    return httpx.get(f"{base}{path}", timeout=15).json()


def post(path, body=None, base=BETSY, **params):
    return httpx.post(f"{base}{path}", json=body or {}, params=params, timeout=60).json()


def ranking() -> list:
    """Composite ranking for SKU-003 from Betsy's merged supplier view —
    the same formula orchestra's supplier matrix uses (score / lead_days)."""
    options = []
    for s in get("/api/suppliers"):
        if not s["availability"] or SKU not in s.get("catalog", {}):
            continue
        lead = max(s["catalog"][SKU]["lead_days"], 0.1)
        options.append({
            "supplier_id": s["supplier_id"],
            "name": s["name"],
            "score": s["reliability_score"],
            "lead_days": lead,
            "composite": round(s["reliability_score"] / lead, 4),
        })
    options.sort(key=lambda x: x["composite"], reverse=True)
    return options


def print_ranking(label, options):
    print(f"\n  {label}")
    for i, o in enumerate(options[:4]):
        marker = "->" if i == 0 else "  "
        print(f"   {marker} {o['name']:<22} score={o['score']:.4f} "
              f"lead={o['lead_days']:.0f}d composite={o['composite']:.4f}")


def main() -> int:
    print("=" * 60)
    print("LONG-TERM LEARNING EVIDENCE — two-service architecture")
    print("=" * 60)

    try:
        health = get("/health")
    except Exception:
        print("ERROR: Betsy not reachable. Start both services first.")
        return 1
    if not health.get("world_up", True):
        print("ERROR: world service not reachable from Betsy.")
        return 1

    print("\n[1] Reset world, pause clock, wait for score bootstrap")
    post("/api/sim/reset")
    post("/api/sim/clock/pause")
    time.sleep(7)  # agent loop bootstraps scores from seeded history

    baseline = ranking()
    print_ranking("Baseline ranking (learned from seeded history):", baseline)
    baseline_winner = baseline[0]["supplier_id"]

    print("\n[2] Forcing 8 delivery rounds via the world admin hook")
    for supplier_id, lateness, label in ROUNDS:
        po = post("/api/purchase-orders", body={
            "supplier_id": supplier_id, "sku_id": SKU,
            "quantity": 50, "unit_price": 12.0,
            "reason": "long-term learning evidence", "requested_by": "test-script",
        }, base=WORLD)
        actual = (datetime.fromisoformat(po["expected_delivery"])
                  + timedelta(days=lateness)).date().isoformat()
        httpx.patch(
            f"{WORLD}/api/purchase-orders/{po['po_id']}/status",
            params={"status": "delivered", "actual_delivery": actual},
            timeout=15,
        )
        print(f"    {label}: {po['po_id']} delivered {actual}")

    print("\n[3] Stepping 1 sim day so Betsy's loop observes the deliveries")
    post("/api/sim/clock/step", days=1)
    time.sleep(8)  # loop poll + EMA processing

    after = ranking()
    print_ranking("Ranking after learning:", after)
    new_winner = after[0]["supplier_id"]

    scores = get("/api/suppliers/scores")
    print("\n  Learned scores:")
    for sid, name in FOCUS.items():
        s = scores.get(sid, {})
        print(f"    {name:<12} {s.get('reliability_score', '?')} "
              f"({s.get('deliveries_observed', 0)} deliveries observed)")

    flipped = baseline_winner == "SUP-003" and new_winner == "SUP-001"
    print("\n" + ("PASS: recommendation flipped QuickShip -> FastParts after bad deliveries"
                  if flipped else
                  f"FAIL: expected flip SUP-003 -> SUP-001, got {baseline_winner} -> {new_winner}"))
    print("=" * 60)
    return 0 if flipped else 1


if __name__ == "__main__":
    sys.exit(main())
