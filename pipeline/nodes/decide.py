"""Stage 4 -- convert evaluated items into decisions. LLM provides reasoning."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import call_json, get_llm
from pipeline.state import PipelineState

MAX_AUTO_USD = float(os.getenv("MAX_AUTO_USD", "5000"))


def run(evaluated: list, llm=None) -> dict:
    decisions = []
    if llm is None:
        llm = get_llm()
    for item in evaluated:
        decisions.append(_decide(item, llm))
    return {"decisions": decisions}


def node(state: PipelineState) -> dict:
    try:
        llm = get_llm()
        return run(state["evaluated"], llm)
    except Exception as exc:
        return {"errors": [f"decide: {exc}"], "decisions": []}


# ── Decision logic ────────────────────────────────────────────────────────────

def _decide(item: dict, llm) -> dict:
    ctype = item["condition"]["type"]

    # Duplicates and price spikes always require human -- no LLM needed
    if ctype == "duplicate_invoice":
        return {
            "action": "flag_duplicate",
            "requires_human": True,
            "auto_approved": False,
            "confidence": item["confidence"],
            "reasoning": item["reasoning"],
            "item": item,
        }

    if ctype == "price_spike":
        return {
            "action": "flag_for_approval",
            "requires_human": True,
            "auto_approved": False,
            "confidence": 0.0,
            "reasoning": item["reasoning"],
            "item": item,
        }

    if item["action"] == "escalate":
        return {
            "action": "escalate",
            "requires_human": True,
            "auto_approved": False,
            "confidence": 0.0,
            "reasoning": item["reasoning"],
            "item": item,
        }

    # Stockout with a best supplier -- ask LLM, then apply financial safeguards
    best = item.get("best_supplier", {})
    sku_id = item["condition"]["sku_id"]
    d = item["condition"]["data"]
    qty = d["max_stock"] - d["current_stock"]
    unit_price = best.get("catalog", {}).get(sku_id, {}).get("unit_price") if isinstance(best.get("catalog"), dict) else best.get("unit_price", 0)
    # Fallback: get unit_price from ranked_suppliers if not on best dict
    if not unit_price and item.get("ranked_suppliers"):
        unit_price = item["ranked_suppliers"][0].get("unit_price", 0)
    po_total = qty * (unit_price or 0)

    result = call_json(
        llm,
        system=(
            "You are a procurement decision agent. Return ONLY valid JSON -- no markdown:\n"
            '{"action": "generate_po|flag_for_approval|escalate|no_action", '
            '"confidence": 0.0-1.0, "reasoning": "...", "requires_human": true|false}\n'
            "Rules you MUST follow:\n"
            "- price_spike conditions always require human approval\n"
            "- duplicate invoices always require human review\n"
            f"- auto-approve only if PO total is under ${MAX_AUTO_USD:,.0f}"
        ),
        user=(
            f"Condition: {item['condition']['type']} | SKU: {sku_id}\n"
            f"Days remaining: {d.get('days_remaining', 'N/A')}\n"
            f"Best supplier: {best.get('name', 'N/A')}\n"
            f"Estimated PO total: ${po_total:,.2f} (qty={qty} × ${unit_price:.2f})\n"
            f"Evaluation reasoning: {item['reasoning'][:200]}\n\n"
            "What action should be taken?"
        ),
    )

    if result.get("fallback"):
        # Rule-based fallback
        requires_human = po_total > MAX_AUTO_USD
        return {
            "action": "generate_po",
            "requires_human": requires_human,
            "auto_approved": not requires_human,
            "confidence": item["confidence"],
            "reasoning": f"Rule-based fallback. PO total ${po_total:,.2f}.",
            "po_total": po_total,
            "qty": qty,
            "unit_price": unit_price,
            "item": item,
        }

    action = result.get("action", "generate_po")
    requires_human = bool(result.get("requires_human", po_total > MAX_AUTO_USD))
    if po_total > MAX_AUTO_USD:
        requires_human = True  # financial safeguard cannot be overridden

    return {
        "action": action,
        "requires_human": requires_human,
        "auto_approved": not requires_human,
        "confidence": float(result.get("confidence", 0.8)),
        "reasoning": result.get("reasoning", ""),
        "po_total": po_total,
        "qty": qty,
        "unit_price": unit_price,
        "item": item,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from shared import api_client as api
    from pipeline.nodes.detect import run as detect_run
    from pipeline.nodes.evaluate import run as evaluate_run

    print("\n" + "=" * 60)
    print("PIPELINE -- Stage: decide")
    print("=" * 60)

    offline = not api.is_server_up()
    inventory = api.load_inventory() if offline else api.get_inventory()
    suppliers = api.load_suppliers() if offline else api.get_suppliers()
    all_pos   = api.load_purchase_orders() if offline else api.get_purchase_orders()
    invoices  = api.load_invoices() if offline else api.get_invoices()

    detected = detect_run(inventory, suppliers, all_pos, invoices)["detected"]
    llm = get_llm()
    evaluated = evaluate_run(detected, suppliers, llm)["evaluated"]

    t0 = time.time()
    result = run(evaluated, llm)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.1f}s\n")

    for dec in result["decisions"]:
        status = "AUTO" if dec["auto_approved"] else "NEEDS HUMAN"
        print(f"  [{dec['action'].upper()}] {status} -- confidence={dec['confidence']:.0%}")
        print(f"    Reasoning: {dec['reasoning'][:120]}")
        if dec.get("po_total"):
            print(f"    PO total: ${dec['po_total']:,.2f}")
        print()
    print("=" * 60)
