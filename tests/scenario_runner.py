"""
Scenario runner — injects each test scenario via the API, runs the agent stub,
and validates the output against the expected action in the scenario file.

Run with: python tests/scenario_runner.py
The mock server must be running at localhost:8000.
"""
import json
from pathlib import Path

import httpx

API = "http://localhost:8000"
SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"

SCENARIOS = ["stockout_warning", "price_spike", "duplicate_invoice", "supplier_oos"]


# ── Agent stub ────────────────────────────────────────────────────────────────
def agent_decide(inventory: list, suppliers: list, invoices: list, purchase_orders: list) -> dict:
    """
    Placeholder agent decision function.
    In Week 2 this is replaced by the real LangGraph agent that calls this API.
    For now it contains hand-coded logic to validate the test harness.
    """

    # 1. Duplicate invoice check
    dupes = _find_duplicates(invoices)
    if dupes:
        return {
            "action": "flag_duplicate",
            "duplicates": dupes,
            "reason": f"{len(dupes)} duplicate invoice pair(s) detected",
        }

    # 2. Price spike check — compare best current quote vs historical PO average
    sku_historical = {}
    for po in purchase_orders:
        sku_historical.setdefault(po["sku_id"], []).append(po["unit_price"])

    for sku_id, prices in sku_historical.items():
        historical_avg = sum(prices) / len(prices)
        current_quotes = [
            sup["catalog"][sku_id]["unit_price"]
            for sup in suppliers
            if sku_id in sup.get("catalog", {}) and sup["availability"]
        ]
        if not current_quotes:
            continue
        best_quote = min(current_quotes)
        if best_quote > historical_avg * 1.30:
            pct = (best_quote / historical_avg - 1) * 100
            return {
                "action": "flag_for_approval",
                "sku_id": sku_id,
                "reason": (
                    f"Price spike: best quote ${best_quote:.2f} is {pct:.0f}% above "
                    f"historical avg ${historical_avg:.2f}"
                ),
            }

    # 3. Stockout / reorder check
    critical = [
        item for item in inventory
        if item["current_stock"] < item["reorder_point"]
    ]
    if not critical:
        return {"action": "no_action", "reason": "All inventory levels healthy"}

    item = sorted(critical, key=lambda x: x["current_stock"] / max(x["reorder_point"], 1))[0]

    available = [
        sup for sup in suppliers
        if sup["availability"] and item["sku_id"] in sup.get("catalog", {})
    ]
    if not available:
        return {
            "action": "escalate",
            "sku_id": item["sku_id"],
            "reason": f"No available supplier for {item['sku_id']} — escalating to human",
        }

    def _score(sup):
        entry = sup["catalog"][item["sku_id"]]
        return sup["reliability_score"] / entry["lead_days"]

    best_supplier = max(available, key=_score)
    entry = best_supplier["catalog"][item["sku_id"]]

    return {
        "action": "generate_po",
        "sku_id": item["sku_id"],
        "supplier": best_supplier["name"],
        "supplier_id": best_supplier["supplier_id"],
        "unit_price": entry["unit_price"],
        "lead_days": entry["lead_days"],
        "reason": (
            f"Stock {item['current_stock']} below reorder {item['reorder_point']} "
            f"({item['current_stock'] / item['daily_usage_avg']:.1f} days remaining)"
        ),
    }


def _find_duplicates(invoices: list) -> list:
    from datetime import datetime
    dupes = []
    seen = set()
    for i, inv in enumerate(invoices):
        for j, other in enumerate(invoices):
            if i >= j:
                continue
            key = tuple(sorted([inv["invoice_id"], other["invoice_id"]]))
            if key in seen:
                continue
            if inv["supplier_id"] != other["supplier_id"]:
                continue
            if abs(inv["total_amount"] - other["total_amount"]) > 0.01:
                continue
            try:
                d1 = datetime.fromisoformat(inv["date"])
                d2 = datetime.fromisoformat(other["date"])
            except ValueError:
                continue
            if abs((d1 - d2).days) <= 60:
                seen.add(key)
                dupes.append({"invoice_1": inv["invoice_id"], "invoice_2": other["invoice_id"]})
    return dupes


# ── Runner ────────────────────────────────────────────────────────────────────
def run_scenario(name: str) -> bool:
    print(f"\n{'=' * 60}")
    print(f"Scenario : {name}")

    scenario_path = SCENARIOS_DIR / f"{name}.json"
    scenario = json.loads(scenario_path.read_text())
    expected_action = scenario.get("expected_agent_action")
    print(f"Expected : {expected_action}")
    print(f"Desc     : {scenario.get('description', '')[:80]}...")

    r = httpx.post(f"{API}/api/scenario/{name}", timeout=5.0)
    if r.status_code != 200:
        print(f"FAIL — could not inject scenario (HTTP {r.status_code})")
        return False

    inventory = httpx.get(f"{API}/api/inventory", timeout=5.0).json()
    suppliers = httpx.get(f"{API}/api/suppliers", timeout=5.0).json()
    invoices = httpx.get(f"{API}/api/invoices", timeout=5.0).json()
    purchase_orders = httpx.get(f"{API}/api/purchase-orders", timeout=5.0).json()

    decision = agent_decide(inventory, suppliers, invoices, purchase_orders)
    print(f"Decision : {decision['action']} — {decision.get('reason', '')[:80]}")

    passed = decision["action"] == expected_action
    print(f"Result   : {'PASS' if passed else 'FAIL'}")
    if not passed:
        print(f"          expected='{expected_action}'  got='{decision['action']}'")

    httpx.post(f"{API}/api/scenario/reset", timeout=5.0)
    return passed


if __name__ == "__main__":
    print("Betsy Scenario Runner")
    print(f"API: {API}")

    try:
        httpx.get(f"{API}/", timeout=3.0)
    except httpx.ConnectError:
        print(f"\nERROR: Cannot connect to {API}")
        print("Start the server first:  uvicorn server.main:app --reload --port 8000")
        raise SystemExit(1)

    results = []
    for scenario_name in SCENARIOS:
        try:
            passed = run_scenario(scenario_name)
            results.append((scenario_name, passed))
        except Exception as exc:
            print(f"ERROR in {scenario_name}: {exc}")
            results.append((scenario_name, False))

    print(f"\n{'=' * 60}")
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    print(f"Results: {passed_count}/{total} passed")
    for scenario_name, passed in results:
        mark = "PASS" if passed else "FAIL"
        print(f"  {mark}  {scenario_name}")
