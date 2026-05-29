"""
Orchestra Agent 4 -- PO Manager
The only agent that writes to the API. Serial execution only.
DRY_RUN=True by default -- set env var DRY_RUN=false to enable writes.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from orchestra.state import OrchestraState

AGENT_NAME = "po_manager"
DRY_RUN    = os.getenv("DRY_RUN", "true").lower() != "false"


def run(decisions: list, brief: dict) -> list:
    """Execute decisions. Returns list of action result dicts."""
    actions = []
    for dec in decisions:
        actions.append(_execute(dec, brief))
    return actions


def _execute(decision: dict, brief: dict) -> dict:
    action = decision["action"]

    if not decision.get("auto_approved", False):
        return {
            "action": action,
            "status": "pending_human_review",
            "executed": False,
            "decision_id": decision.get("id", "?"),
        }

    if action != "generate_po":
        return {"action": action, "status": "logged", "executed": True}

    finding = decision.get("finding", {})
    sku_id  = finding.get("sku_id", "UNKNOWN")

    # Find recommended supplier from supplier scout data
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

    inv_item = next((i for i in brief["inventory"] if i["sku_id"] == sku_id), {})
    qty      = inv_item.get("max_stock", 0) - inv_item.get("current_stock", 0)
    price    = rec_sup.get("unit_price", 0)

    payload = {
        "supplier_id":  rec_sup.get("supplier_id", "UNKNOWN"),
        "sku_id":       sku_id,
        "quantity":     qty,
        "unit_price":   price,
        "reason":       decision.get("reasoning", "")[:200],
        "requested_by": "betsy-orchestra",
    }

    if DRY_RUN:
        return {"action": action, "status": "dry_run", "executed": False, "payload": payload}

    try:
        resp = api._post_purchase_order(payload)
        return {"action": action, "status": "created", "executed": True, "response": resp}
    except Exception as exc:
        return {"action": action, "status": "error", "executed": False, "error": str(exc)}


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
    result = _execute(mock_dec, brief)
    import json
    print(json.dumps(result, indent=2))
    print("=" * 60)
