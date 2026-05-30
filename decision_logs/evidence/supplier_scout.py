"""
Orchestra Agent 2 -- Supplier Scout
Scores suppliers, detects price spikes, flags unavailability.
LLM explains tradeoffs and red flags.
Read-only: works entirely from the brief.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import call_json, get_llm
from orchestra.state import OrchestraState

AGENT_NAME = "supplier_scout"
PRICE_SPIKE_THRESHOLD = 0.30


def run(brief: dict, llm=None) -> list:
    """Returns list of Finding dicts."""
    if llm is None:
        llm = get_llm()

    inventory = brief["inventory"]
    suppliers  = brief["suppliers"]
    all_pos    = brief.get("all_pos", [])

    matrix = _build_matrix(inventory, suppliers)
    findings = []

    # Price spike detection
    sku_prices: dict = {}
    for po in all_pos:
        sku_prices.setdefault(po["sku_id"], []).append(po["unit_price"])

    for sku_id, prices in sku_prices.items():
        avg = sum(prices) / len(prices)
        options = matrix.get(sku_id, [])
        quotes = [o["unit_price"] for o in options if o["available"]]
        if not quotes:
            continue
        best = min(quotes)
        if best > avg * (1 + PRICE_SPIKE_THRESHOLD):
            pct = (best / avg - 1) * 100
            findings.append({
                "agent": AGENT_NAME,
                "type": "price_spike",
                "severity": "warning",
                "sku_id": sku_id,
                "confidence": 0.0,
                "data": {
                    "best_quote": round(best, 2),
                    "historical_avg": round(avg, 2),
                    "pct_above": round(pct, 1),
                    "options": options,
                },
                "reasoning": (
                    f"Best quote ${best:.2f} is {pct:.0f}% above "
                    f"historical avg ${avg:.2f}. Human approval required."
                ),
                "recommendation": "flag_for_approval",
            })

    # Unavailability detection for stockout SKUs
    critical_skus = {
        item["sku_id"]
        for item in inventory
        if item["current_stock"] < item["reorder_point"]
    }
    for sku_id in critical_skus:
        options = matrix.get(sku_id, [])
        if options and not any(o["available"] for o in options):
            findings.append({
                "agent": AGENT_NAME,
                "type": "supplier_unavailable",
                "severity": "critical",
                "sku_id": sku_id,
                "confidence": 1.0,
                "data": {"options": options},
                "reasoning": f"All {len(options)} supplier(s) unavailable for {sku_id}.",
                "recommendation": "escalate",
            })

    # LLM ranking for critical SKUs that have available suppliers
    for sku_id in critical_skus:
        options = [o for o in matrix.get(sku_id, []) if o["available"]]
        if not options:
            continue
        item_data = next((i for i in inventory if i["sku_id"] == sku_id), {})
        daily = max(item_data.get("daily_usage_avg", 1), 0.1)
        days  = round(item_data.get("current_stock", 0) / daily, 1)

        result = call_json(
            llm,
            system=(
                "You are a supplier evaluation specialist. Return ONLY valid JSON -- no markdown:\n"
                '{"recommended_supplier_id": "...", "confidence": 0.0-1.0, '
                '"tradeoff_summary": "...", "red_flags": []}'
            ),
            user=(
                f"SKU needed: {sku_id}\n"
                f"Urgency: {days} days of stock remaining\n\n"
                f"Available suppliers (sorted by score = reliability / lead_days):\n"
                f"{json.dumps(options, indent=2)}\n\n"
                "Select the best supplier. Explain the reliability vs speed vs cost tradeoff. "
                "Flag any concerns."
            ),
        )

        if result.get("fallback"):
            rec = options[0]
            tradeoff = f"Rule-based: {rec['name']} (score={rec['score']})"
            red_flags = []
            confidence = 0.7
        else:
            rec_id     = result.get("recommended_supplier_id", options[0]["supplier_id"])
            rec        = next((o for o in options if o["supplier_id"] == rec_id), options[0])
            tradeoff   = result.get("tradeoff_summary", "")
            red_flags  = result.get("red_flags", [])
            confidence = float(result.get("confidence", 0.8))

        findings.append({
            "agent": AGENT_NAME,
            "type": "supplier_recommendation",
            "severity": "info",
            "sku_id": sku_id,
            "confidence": confidence,
            "data": {
                "recommended_supplier": rec,
                "all_options": options,
                "red_flags": red_flags,
            },
            "reasoning": tradeoff,
            "recommendation": "use_supplier",
        })

    return findings


def _build_matrix(inventory: list, suppliers: list) -> dict:
    """Returns {sku_id: [{supplier_id, name, score, unit_price, lead_days, available}]}"""
    matrix: dict = {}
    for sup in suppliers:
        for sku_id, entry in sup.get("catalog", {}).items():
            lead = entry.get("lead_days", 999)
            score = round(sup["reliability_score"] / max(lead, 0.1), 3)
            matrix.setdefault(sku_id, []).append({
                "supplier_id": sup["supplier_id"],
                "name": sup["name"],
                "score": score,
                "unit_price": entry["unit_price"],
                "lead_days": lead,
                "reliability": sup["reliability_score"],
                "available": sup["availability"],
            })
    for sku_id in matrix:
        matrix[sku_id].sort(key=lambda x: x["score"], reverse=True)
    return matrix


def node(state: OrchestraState) -> dict:
    try:
        llm = get_llm()
        findings = run(state["brief"], llm)
        return {"supplier_findings": findings}
    except Exception as exc:
        return {"errors": [f"{AGENT_NAME}: {exc}"], "supplier_findings": []}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from shared import api_client as api

    print("\n" + "=" * 60)
    print("ORCHESTRA -- Agent: supplier_scout")
    print("=" * 60)

    offline = not api.is_server_up()
    brief = {
        "inventory": api.load_inventory() if offline else api.get_inventory(),
        "suppliers": api.load_suppliers() if offline else api.get_suppliers(),
        "all_pos":   api.load_purchase_orders() if offline else api.get_purchase_orders(),
        "invoices":  api.load_invoices() if offline else api.get_invoices(),
    }

    llm = get_llm()
    t0 = time.time()
    findings = run(brief, llm)
    elapsed = time.time() - t0

    print(f"Time: {elapsed:.1f}s | Findings: {len(findings)}\n")
    for f in findings:
        print(f"  [{f['type'].upper()}] SKU={f['sku_id']} | confidence={f['confidence']:.0%}")
        print(f"    Reasoning: {f['reasoning'][:120]}")
        if f.get("data", {}).get("red_flags"):
            print(f"    Red flags: {f['data']['red_flags']}")
        print()
    print("=" * 60)
