"""Stage 5 -- execute auto-approved decisions. DRY_RUN=True by default."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from pipeline.state import PipelineState

DRY_RUN = os.getenv("DRY_RUN", "true").lower() != "false"


def run(decisions: list) -> dict:
    actions = []
    for dec in decisions:
        actions.append(_execute(dec))
    return {"actions": actions}


def node(state: PipelineState) -> dict:
    try:
        return run(state["decisions"])
    except Exception as exc:
        return {"errors": [f"act: {exc}"], "actions": []}


def _queue_for_approval(decision: dict) -> None:
    import uuid
    from datetime import datetime
    item = decision.get("item", {})
    condition = item.get("condition", {})
    best = item.get("best_supplier") or {}
    sku_id = condition.get("sku_id", "")
    payload = None
    if decision["action"] == "generate_po":
        payload = {
            "supplier_id": best.get("supplier_id", "UNKNOWN"),
            "sku_id": sku_id,
            "quantity": decision.get("qty", 0),
            "unit_price": decision.get("unit_price", 0),
            "reason": decision.get("reasoning", "")[:200],
            "requested_by": "betsy-pipeline",
        }
    api.queue_approval({
        "decision_id": str(uuid.uuid4()),
        "status": "pending",
        "action": decision["action"],
        "sku_id": sku_id,
        "supplier_id": best.get("supplier_id", ""),
        "po_total": decision.get("po_total", 0),
        "qty": decision.get("qty", 0),
        "unit_price": decision.get("unit_price", 0),
        "confidence": decision.get("confidence", 0.5),
        "reasoning": decision.get("reasoning", ""),
        "created_at": datetime.now().isoformat(),
        "payload": payload,
    })


def _execute(decision: dict) -> dict:
    action = decision["action"]
    item = decision.get("item", {})
    condition = item.get("condition", {})
    best = item.get("best_supplier") or {}
    sku_id = condition.get("sku_id", "N/A")

    if not decision.get("auto_approved", False):
        _queue_for_approval(decision)
        return {
            "action": action,
            "status": "pending_human_review",
            "executed": False,
            "note": "Queued to /api/approvals",
        }

    if action == "generate_po":
        payload = {
            "supplier_id": best.get("supplier_id", "UNKNOWN"),
            "sku_id": sku_id,
            "quantity": decision.get("qty", 0),
            "unit_price": decision.get("unit_price", 0),
            "reason": decision.get("reasoning", "")[:200],
            "requested_by": "betsy-pipeline",
        }
        if DRY_RUN:
            return {"action": action, "status": "dry_run", "executed": False, "payload": payload}
        try:
            resp = api._post_purchase_order(payload)
            return {"action": action, "status": "created", "executed": True, "response": resp}
        except Exception as exc:
            return {"action": action, "status": "error", "executed": False, "error": str(exc)}

    if action in ("flag_duplicate", "flag_for_approval", "escalate"):
        return {"action": action, "status": "logged", "executed": True}

    return {"action": action, "status": "no_op", "executed": False}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from shared import api_client as api
    from pipeline.nodes.detect import run as detect_run
    from pipeline.nodes.evaluate import run as evaluate_run
    from pipeline.nodes.decide import run as decide_run
    from shared.llm import get_llm

    print("\n" + "=" * 60)
    print(f"PIPELINE -- Stage: act  (DRY_RUN={DRY_RUN})")
    print("=" * 60)

    offline = not api.is_server_up()
    inventory = api.load_inventory() if offline else api.get_inventory()
    suppliers = api.load_suppliers() if offline else api.get_suppliers()
    all_pos   = api.load_purchase_orders() if offline else api.get_purchase_orders()
    invoices  = api.load_invoices() if offline else api.get_invoices()

    llm = get_llm()
    detected  = detect_run(inventory, suppliers, all_pos, invoices)["detected"]
    evaluated = evaluate_run(detected, suppliers, llm)["evaluated"]
    decisions = decide_run(evaluated, llm)["decisions"]

    result = run(decisions)
    for a in result["actions"]:
        print(f"  [{a['action'].upper()}] status={a['status']}  executed={a['executed']}")
        if a.get("payload"):
            import json
            print(f"    Payload: {json.dumps(a['payload'], indent=4)}")
    print("=" * 60)
