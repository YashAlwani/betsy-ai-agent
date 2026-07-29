"""
Orchestra Agent 4 -- PO Manager
The only agent that writes to the outside world. Serial execution only.

Auto-approved POs are created in the world directly (the approvals queue and
MAX_AUTO_USD cap are the safety gates). Decisions requiring a human are queued
in Betsy's approvals with enough payload to execute on approval.
Set DRY_RUN=true to disable all writes (testing).
"""
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from orchestra.state import OrchestraState

AGENT_NAME = "po_manager"
DRY_RUN    = os.getenv("DRY_RUN", "false").lower() == "true"


def run(decisions: list, brief: dict) -> list:
    """Execute decisions. Returns list of action result dicts."""
    actions = []
    pending = _pending_signatures()
    for dec in decisions:
        actions.append(_execute(dec, brief, pending))
    return actions


def _pending_signatures() -> set:
    """Signatures of already-pending approvals, to avoid re-queuing the same
    situation every run while the human hasn't answered yet."""
    try:
        return {
            (a.get("action"), a.get("sku_id"), a.get("supplier_id"))
            for a in api_get_pending()
        }
    except Exception:
        return set()


def api_get_pending() -> list:
    import httpx
    return httpx.get(f"{api.API_BASE}/api/approvals", timeout=5.0).json()


def _execute(decision: dict, brief: dict, pending: set) -> dict:
    action = decision["action"]
    finding = decision.get("finding", {})
    sku_id  = finding.get("sku_id")

    if not decision.get("auto_approved", False):
        return _queue_for_human(decision, brief, pending)

    if action != "generate_po":
        return {"action": action, "status": "logged", "executed": True}

    sup_data = finding.get("supplier_data") or {}
    rec_sup  = sup_data.get("recommended_supplier") or {}

    errors = _validate(sku_id, rec_sup, brief)
    if errors:
        return {
            "action": action,
            "status": "validation_failed",
            "executed": False,
            "errors": errors,
        }

    payload = _po_payload(decision, brief)

    if DRY_RUN:
        return {"action": action, "status": "dry_run", "executed": False, "payload": payload}

    try:
        resp = api._post_purchase_order(payload)
        return {"action": action, "status": "created", "executed": True, "response": resp}
    except Exception as exc:
        return {"action": action, "status": "error", "executed": False, "error": str(exc)}


def _queue_for_human(decision: dict, brief: dict, pending: set) -> dict:
    action  = decision["action"]
    finding = decision.get("finding", {})
    data    = finding.get("data", {})
    sku_id  = finding.get("sku_id")

    payload = {}
    supplier_id = None
    qty = unit_price = po_total = 0

    if action == "generate_po":
        payload = _po_payload(decision, brief)
        supplier_id = payload.get("supplier_id")
        qty         = payload.get("quantity", 0)
        unit_price  = payload.get("unit_price", 0)
        po_total    = decision.get("po_total") or round(qty * unit_price, 2)
    elif action == "flag_duplicate":
        supplier_id = data.get("supplier_id")
        po_total    = data.get("amount", 0)
        payload = {
            "invoice_id": data.get("newer_invoice") or data.get("invoice_2"),
            "invoice_pair": [data.get("invoice_1"), data.get("invoice_2")],
        }
    elif action in ("flag_for_approval", "escalate"):
        supplier_id = data.get("supplier_id")

    # Duplicates dedupe permanently on the invoice pair; everything else
    # dedupes on (action, sku, supplier) while still pending.
    if action == "flag_duplicate":
        pair = "-".join(sorted(filter(None, payload.get("invoice_pair", []))))
        decision_id = "dup-" + hashlib.sha1(pair.encode()).hexdigest()[:16]
    else:
        if (action, sku_id, supplier_id) in pending:
            return {"action": action, "status": "already_pending", "executed": False}
        decision_id = None  # let Betsy assign a uuid

    item = {
        "action": action,
        "sku_id": sku_id,
        "supplier_id": supplier_id,
        "po_total": po_total,
        "qty": qty,
        "unit_price": unit_price,
        "confidence": decision.get("confidence", 0.5),
        "reasoning": decision.get("reasoning", "")[:400],
        "payload": payload or None,
    }
    if decision_id:
        item["decision_id"] = decision_id

    if DRY_RUN:
        return {"action": action, "status": "dry_run_queue", "executed": False, "item": item}

    resp = api.queue_approval(item)
    return {
        "action": action,
        "status": "pending_human_review",
        "executed": False,
        "decision_id": resp.get("decision_id", decision_id),
    }


def _po_payload(decision: dict, brief: dict) -> dict:
    finding  = decision.get("finding", {})
    sku_id   = finding.get("sku_id", "UNKNOWN")
    sup_data = finding.get("supplier_data") or {}
    rec_sup  = sup_data.get("recommended_supplier") or {}
    inv_item = next((i for i in brief.get("inventory", []) if i["sku_id"] == sku_id), {})
    qty      = max(0, inv_item.get("max_stock", 0) - inv_item.get("current_stock", 0))
    return {
        "supplier_id":  rec_sup.get("supplier_id", "UNKNOWN"),
        "sku_id":       sku_id,
        "quantity":     qty,
        "unit_price":   rec_sup.get("unit_price", 0),
        "reason":       decision.get("reasoning", "")[:200],
        "requested_by": "betsy-orchestra",
    }


def _validate(sku_id: str, supplier: dict, brief: dict) -> list:
    errors = []
    if not sku_id or sku_id == "UNKNOWN":
        errors.append("missing sku_id")
    if not supplier:
        errors.append("no supplier selected")
    elif not supplier.get("available", True):
        errors.append(f"supplier {supplier.get('supplier_id')} is unavailable")
    # Check for existing open PO
    open_pos = brief.get("open_pos", [])
    if any(po["sku_id"] == sku_id for po in open_pos):
        errors.append(f"open PO already exists for {sku_id}")
    return errors


def node(state: OrchestraState) -> dict:
    try:
        actions = run(state["decisions"], state["brief"])
        return {"actions": actions}
    except Exception as exc:
        return {"errors": [f"{AGENT_NAME}: {exc}"], "actions": []}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(f"ORCHESTRA -- Agent: po_manager  (DRY_RUN={DRY_RUN})")
    print("=" * 60)
    print("PO Manager only executes decisions passed to it.")
    print("Run the full orchestra or orchestrate node to generate decisions first.")
    print()
    print("To test with a mock decision:")
    mock_dec = {
        "action": "generate_po",
        "auto_approved": True,
        "reasoning": "Mock decision for testing",
        "finding": {
            "sku_id": "SKU-003",
            "supplier_data": {
                "recommended_supplier": {
                    "supplier_id": "SUP-003",
                    "name": "QuickShip Express",
                    "unit_price": 15.00,
                    "lead_days": 1,
                    "available": True,
                }
            },
        },
    }
    from shared import api_client as api
    offline = not api.is_server_up()
    brief = {
        "inventory": api.load_inventory() if offline else api.get_inventory(),
        "open_pos": [],
    }
    result = _execute(mock_dec, brief, set())
    import json
    print(json.dumps(result, indent=2))
    print("=" * 60)
