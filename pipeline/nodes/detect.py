"""Stage 2 -- detect conditions from ingested data. No LLM."""
import sys
from datetime import datetime
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.state import PipelineState

PRICE_SPIKE_THRESHOLD = 0.30  # 30% above historical avg (matches stub)


def run(inventory: list, suppliers: list, all_pos: list, invoices: list) -> dict:
    """Returns dict with detected conditions list."""
    conditions = []
    conditions.extend(_detect_duplicates(invoices))
    conditions.extend(_detect_price_spikes(inventory, all_pos, suppliers))
    conditions.extend(_detect_stockouts(inventory))
    return {"detected": conditions}


def node(state: PipelineState) -> dict:
    try:
        return run(state["inventory"], state["suppliers"], state["all_pos"], state["invoices"])
    except Exception as exc:
        return {"errors": [f"detect: {exc}"], "detected": []}


# ── Detection functions ───────────────────────────────────────────────────────

def _detect_duplicates(invoices: list) -> List[dict]:
    conditions = []
    seen = set()
    for i, a in enumerate(invoices):
        for j, b in enumerate(invoices):
            if i >= j:
                continue
            key = tuple(sorted([a["invoice_id"], b["invoice_id"]]))
            if key in seen:
                continue
            if a["supplier_id"] != b["supplier_id"]:
                continue
            if abs(a["total_amount"] - b["total_amount"]) > 0.01:
                continue
            try:
                d1 = datetime.fromisoformat(a["date"])
                d2 = datetime.fromisoformat(b["date"])
            except (ValueError, KeyError):
                continue
            days_apart = abs((d1 - d2).days)
            if days_apart > 60:
                continue
            seen.add(key)
            conditions.append({
                "type": "duplicate_invoice",
                "severity": "warning",
                "sku_id": a.get("sku_id"),
                "data": {
                    "invoice_1": a["invoice_id"],
                    "invoice_2": b["invoice_id"],
                    "supplier_id": a["supplier_id"],
                    "amount": a["total_amount"],
                    "days_apart": days_apart,
                },
            })
    return conditions


def _detect_price_spikes(inventory: list, all_pos: list, suppliers: list) -> List[dict]:
    # Build per-SKU historical average from PO history
    sku_prices: dict = {}
    for po in all_pos:
        sku_prices.setdefault(po["sku_id"], []).append(po["unit_price"])

    conditions = []
    for sku_id, prices in sku_prices.items():
        historical_avg = sum(prices) / len(prices)
        current_quotes = [
            sup["catalog"][sku_id]["unit_price"]
            for sup in suppliers
            if sup["availability"] and sku_id in sup.get("catalog", {})
        ]
        if not current_quotes:
            continue
        best_quote = min(current_quotes)
        if best_quote > historical_avg * (1 + PRICE_SPIKE_THRESHOLD):
            pct = (best_quote / historical_avg - 1) * 100
            conditions.append({
                "type": "price_spike",
                "severity": "warning",
                "sku_id": sku_id,
                "data": {
                    "best_quote": round(best_quote, 2),
                    "historical_avg": round(historical_avg, 2),
                    "pct_above": round(pct, 1),
                    "threshold_pct": PRICE_SPIKE_THRESHOLD * 100,
                },
            })
    return conditions


def _detect_stockouts(inventory: list) -> List[dict]:
    conditions = []
    for item in inventory:
        if item["current_stock"] < item["reorder_point"]:
            daily = max(item.get("daily_usage_avg", 1), 0.1)
            days = item["current_stock"] / daily
            conditions.append({
                "type": "stockout",
                "severity": "critical" if days < 2.0 else "warning",
                "sku_id": item["sku_id"],
                "data": {
                    "name": item["name"],
                    "current_stock": item["current_stock"],
                    "reorder_point": item["reorder_point"],
                    "max_stock": item["max_stock"],
                    "daily_usage_avg": daily,
                    "days_remaining": round(days, 1),
                    "unit_cost_avg": item.get("unit_cost_avg", 0),
                },
            })
    return conditions


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    from shared import api_client as api

    print("\n" + "=" * 60)
    print("PIPELINE -- Stage: detect")
    print("=" * 60)

    offline = not api.is_server_up()
    inventory = api.load_inventory() if offline else api.get_inventory()
    suppliers = api.load_suppliers() if offline else api.get_suppliers()
    all_pos   = api.load_purchase_orders() if offline else api.get_purchase_orders()
    invoices  = api.load_invoices() if offline else api.get_invoices()

    result = run(inventory, suppliers, all_pos, invoices)
    conditions = result["detected"]

    print(f"\nDetected {len(conditions)} condition(s):\n")
    for c in conditions:
        icon = "[!!]" if c["severity"] == "critical" else "[!] "
        print(f"  {icon} [{c['type'].upper()}] severity={c['severity']}")
        if c["type"] == "stockout":
            d = c["data"]
            print(f"     SKU {c['sku_id']} -- {d['name']}")
            print(f"     Stock: {d['current_stock']} / Reorder: {d['reorder_point']} / Days left: {d['days_remaining']}")
        elif c["type"] == "price_spike":
            d = c["data"]
            print(f"     SKU {c['sku_id']} -- best quote ${d['best_quote']} vs avg ${d['historical_avg']} (+{d['pct_above']}%)")
        elif c["type"] == "duplicate_invoice":
            d = c["data"]
            print(f"     {d['invoice_1']} & {d['invoice_2']} -- ${d['amount']} -- {d['days_apart']} days apart")

    if not conditions:
        print("  No conditions detected.")
    print("=" * 60)
