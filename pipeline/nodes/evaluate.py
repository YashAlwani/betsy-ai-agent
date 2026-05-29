"""Stage 3 -- score options per condition. LLM explains supplier choice."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import call_json, get_llm
from pipeline.state import PipelineState


def run(detected: list, suppliers: list, llm=None) -> dict:
    """Returns dict with evaluated items list."""
    if llm is None:
        llm = get_llm()
    evaluated = []
    for condition in detected:
        if condition["type"] == "stockout":
            item = _evaluate_stockout(condition, suppliers, llm)
        elif condition["type"] == "price_spike":
            item = _evaluate_price_spike(condition, suppliers)
        elif condition["type"] == "duplicate_invoice":
            item = _evaluate_duplicate(condition, llm)
        else:
            item = {"condition": condition, "action": "no_action", "confidence": 0.5, "reasoning": "unknown type"}
        evaluated.append(item)
    return {"evaluated": evaluated}


def node(state: PipelineState) -> dict:
    try:
        llm = get_llm()
        return run(state["detected"], state["suppliers"], llm)
    except Exception as exc:
        return {"errors": [f"evaluate: {exc}"], "evaluated": []}


# ── Evaluation helpers ────────────────────────────────────────────────────────

def _score_supplier(sup: dict, sku_id: str) -> float:
    entry = sup["catalog"].get(sku_id, {})
    lead = entry.get("lead_days", 999)
    return sup["reliability_score"] / max(lead, 0.1)


def _evaluate_stockout(condition: dict, suppliers: list, llm) -> dict:
    sku_id = condition["sku_id"]
    available = [
        s for s in suppliers
        if s["availability"] and sku_id in s.get("catalog", {})
    ]
    ranked = sorted(available, key=lambda s: _score_supplier(s, sku_id), reverse=True)

    if not ranked:
        return {
            "condition": condition,
            "action": "escalate",
            "best_supplier": None,
            "ranked_suppliers": [],
            "confidence": 0.0,
            "reasoning": "No available supplier carries this SKU.",
        }

    ranked_info = [
        {
            "supplier_id": s["supplier_id"],
            "name": s["name"],
            "score": round(_score_supplier(s, sku_id), 3),
            "unit_price": s["catalog"][sku_id]["unit_price"],
            "lead_days": s["catalog"][sku_id]["lead_days"],
            "reliability": s["reliability_score"],
        }
        for s in ranked[:5]
    ]

    d = condition["data"]
    result = call_json(
        llm,
        system=(
            "You are a procurement analyst. Return ONLY valid JSON -- no markdown, no extra text:\n"
            '{"recommended_supplier_id": "...", "confidence": 0.0-1.0, "reasoning": "..."}'
        ),
        user=(
            f"SKU: {sku_id} -- {d.get('name', '')}\n"
            f"Stock: {d['current_stock']} units | Reorder point: {d['reorder_point']} | "
            f"Days remaining: {d['days_remaining']}\n\n"
            f"Ranked suppliers (score = reliability / lead_days):\n"
            f"{json.dumps(ranked_info, indent=2)}\n\n"
            "Pick the best supplier. Consider urgency, reliability, lead time, and cost."
        ),
    )

    if result.get("fallback"):
        best = ranked[0]
        reasoning = (
            f"Rule-based fallback: {best['name']} "
            f"(score={round(_score_supplier(best, sku_id), 3)})"
        )
        confidence = 0.7
    else:
        rec_id = result.get("recommended_supplier_id", ranked[0]["supplier_id"])
        best = next((s for s in ranked if s["supplier_id"] == rec_id), ranked[0])
        reasoning = result.get("reasoning", "")
        confidence = float(result.get("confidence", 0.8))

    return {
        "condition": condition,
        "action": "generate_po",
        "best_supplier": best,
        "ranked_suppliers": ranked_info,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _evaluate_price_spike(condition: dict, suppliers: list) -> dict:
    sku_id = condition["sku_id"]
    available = [
        {
            "supplier_id": s["supplier_id"],
            "name": s["name"],
            "unit_price": s["catalog"][sku_id]["unit_price"],
            "lead_days": s["catalog"][sku_id]["lead_days"],
        }
        for s in suppliers
        if s["availability"] and sku_id in s.get("catalog", {})
    ]
    available.sort(key=lambda x: x["unit_price"])
    d = condition["data"]
    return {
        "condition": condition,
        "action": "flag_for_approval",
        "best_supplier": available[0] if available else None,
        "ranked_suppliers": available,
        "confidence": 0.0,
        "reasoning": (
            f"Price spike of {d['pct_above']}% above historical average. "
            f"Best quote: ${d['best_quote']} vs avg ${d['historical_avg']}. "
            "Requires human approval before ordering."
        ),
    }


def _evaluate_duplicate(condition: dict, llm) -> dict:
    d = condition["data"]
    result = call_json(
        llm,
        system=(
            "You are a financial auditor. Return ONLY valid JSON -- no markdown, no extra text:\n"
            '{"risk_level": "HIGH|MEDIUM|LOW", "fraud_likelihood": "suspicious|likely_error|unknown", '
            '"confidence": 0.0-1.0, "reasoning": "..."}'
        ),
        user=(
            f"Duplicate invoice pair detected:\n"
            f"  Invoice 1: {d['invoice_1']}\n"
            f"  Invoice 2: {d['invoice_2']}\n"
            f"  Supplier:  {d['supplier_id']}\n"
            f"  Amount:    ${d['amount']}\n"
            f"  Days apart: {d['days_apart']}\n\n"
            "Is this a billing error or potential fraud?"
        ),
    )

    if result.get("fallback"):
        risk = "HIGH" if d["days_apart"] <= 30 else "MEDIUM"
        confidence = 1.0 if risk == "HIGH" else 0.7
        fraud_likelihood = "unknown"
        reasoning = f"Rule-based: {d['days_apart']} days apart → {risk} risk"
    else:
        risk = result.get("risk_level", "MEDIUM")
        confidence = float(result.get("confidence", 0.7))
        fraud_likelihood = result.get("fraud_likelihood", "unknown")
        reasoning = result.get("reasoning", "")

    return {
        "condition": condition,
        "action": "flag_duplicate",
        "best_supplier": None,
        "ranked_suppliers": [],
        "confidence": confidence,
        "reasoning": reasoning,
        "risk_level": risk,
        "fraud_likelihood": fraud_likelihood,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from shared import api_client as api
    from pipeline.nodes.detect import run as detect_run

    print("\n" + "=" * 60)
    print("PIPELINE -- Stage: evaluate")
    print("=" * 60)

    offline = not api.is_server_up()
    inventory = api.load_inventory() if offline else api.get_inventory()
    suppliers = api.load_suppliers() if offline else api.get_suppliers()
    all_pos   = api.load_purchase_orders() if offline else api.get_purchase_orders()
    invoices  = api.load_invoices() if offline else api.get_invoices()

    detected = detect_run(inventory, suppliers, all_pos, invoices)["detected"]
    print(f"Input: {len(detected)} condition(s) from detect stage")

    llm = get_llm()
    t0 = time.time()
    result = run(detected, suppliers, llm)
    elapsed = time.time() - t0

    print(f"LLM: {__import__('shared.llm', fromlist=['OLLAMA_MODEL']).OLLAMA_MODEL} "
          f"@ {__import__('shared.llm', fromlist=['OLLAMA_BASE_URL']).OLLAMA_BASE_URL}")
    print(f"Time: {elapsed:.1f}s\n")

    for item in result["evaluated"]:
        c = item["condition"]
        print(f"  [{c['type'].upper()}] SKU={c.get('sku_id', 'N/A')} → action={item['action']}")
        print(f"    Confidence: {item['confidence']:.0%}")
        if item.get("best_supplier"):
            bs = item["best_supplier"]
            name = bs.get("name", bs.get("supplier_id", "?"))
            print(f"    Best supplier: {name}")
        print(f"    Reasoning: {item['reasoning'][:120]}")
        print()
    print("=" * 60)
