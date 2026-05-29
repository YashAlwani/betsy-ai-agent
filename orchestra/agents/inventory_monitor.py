"""
Orchestra Agent 1 -- Inventory Monitor
Finds stockout risks and assesses urgency with LLM.
Read-only: works entirely from the brief.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import call_json, get_llm
from orchestra.state import OrchestraState

AGENT_NAME = "inventory_monitor"


def run(brief: dict, llm=None) -> list:
    """Returns list of Finding dicts. Callable standalone."""
    if llm is None:
        llm = get_llm()
    inventory = brief["inventory"]
    open_pos   = brief.get("open_pos", [])
    open_skus  = {po["sku_id"] for po in open_pos}

    findings = []
    for item in inventory:
        if item["current_stock"] >= item["reorder_point"]:
            continue
        if item["sku_id"] in open_skus:
            continue  # PO already pending

        daily = max(item.get("daily_usage_avg", 1), 0.1)
        days  = round(item["current_stock"] / daily, 1)

        result = call_json(
            llm,
            system=(
                "You are a warehouse analyst. Return ONLY valid JSON -- no markdown:\n"
                '{"urgency": "critical|high|medium|low", "recommended_qty": int, '
                '"confidence": 0.0-1.0, "reasoning": "..."}'
            ),
            user=(
                f"SKU: {item['sku_id']} -- {item['name']}\n"
                f"Current stock: {item['current_stock']} | Reorder point: {item['reorder_point']} | "
                f"Max stock: {item['max_stock']}\n"
                f"Daily usage: {daily} | Days remaining: {days}\n"
                f"Open POs for this SKU: {item['sku_id'] in open_skus}"
            ),
        )

        if result.get("fallback"):
            urgency    = "critical" if days < 2.0 else "high" if days < 5.0 else "medium"
            rec_qty    = item["max_stock"] - item["current_stock"]
            confidence = min(1.0 / max(days, 0.1) / 10, 1.0)
            reasoning  = f"Rule-based: {days} days remaining"
        else:
            urgency    = result.get("urgency", "high")
            rec_qty    = int(result.get("recommended_qty", item["max_stock"] - item["current_stock"]))
            confidence = float(result.get("confidence", 0.8))
            reasoning  = result.get("reasoning", "")

        findings.append({
            "agent": AGENT_NAME,
            "type": "stockout_risk",
            "severity": "critical" if urgency == "critical" else "warning",
            "sku_id": item["sku_id"],
            "sku_name": item["name"],
            "urgency": urgency,
            "confidence": confidence,
            "recommended_qty": rec_qty,
            "data": {
                "current_stock": item["current_stock"],
                "reorder_point": item["reorder_point"],
                "max_stock": item["max_stock"],
                "days_remaining": days,
                "unit_cost_avg": item.get("unit_cost_avg", 0),
            },
            "reasoning": reasoning,
            "recommendation": "generate_po",
        })

    return findings


def node(state: OrchestraState) -> dict:
    try:
        llm = get_llm()
        findings = run(state["brief"], llm)
        return {"inventory_findings": findings}
    except Exception as exc:
        return {"errors": [f"{AGENT_NAME}: {exc}"], "inventory_findings": []}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from shared import api_client as api

    print("\n" + "=" * 60)
    print("ORCHESTRA -- Agent: inventory_monitor")
    print("=" * 60)

    offline = not api.is_server_up()
    brief = {
        "inventory": api.load_inventory() if offline else api.get_inventory(),
        "suppliers": api.load_suppliers() if offline else api.get_suppliers(),
        "all_pos":   api.load_purchase_orders() if offline else api.get_purchase_orders(),
        "open_pos":  [],
        "invoices":  api.load_invoices() if offline else api.get_invoices(),
    }
    brief["open_pos"] = [po for po in brief["all_pos"] if po.get("status") not in {"delivered", "cancelled"}]

    llm = get_llm()
    t0 = time.time()
    findings = run(brief, llm)
    elapsed = time.time() - t0

    print(f"Time: {elapsed:.1f}s | Findings: {len(findings)}\n")
    for f in findings:
        print(f"  [{f['severity'].upper()}] {f['sku_id']} -- {f['sku_name']}")
        print(f"    Urgency: {f['urgency']} | Days left: {f['data']['days_remaining']} | "
              f"Confidence: {f['confidence']:.0%}")
        print(f"    Reasoning: {f['reasoning'][:120]}")
        print()
    if not findings:
        print("  No stockout risks detected.")
    print("=" * 60)
