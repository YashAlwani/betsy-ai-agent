import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from server import db, notifier
from server.state import state

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("")
def get_approvals():
    return [a for a in state.approvals if a["status"] == "pending"]


@router.post("", status_code=201)
def queue_approval(item: dict):
    if "decision_id" not in item:
        item["decision_id"] = str(uuid.uuid4())
    if "status" not in item:
        item["status"] = "pending"
    if "created_at" not in item:
        item["created_at"] = datetime.now().isoformat()
    state.approvals.append(item)
    db.save_approval(item)

    # Fire desktop + email notification for the queued item.
    # All action types (generate_po, flag_duplicate, flag_for_approval, escalate)
    # use the same approval notification; the action label differentiates them.
    notifier.notify_approval_required(item)

    return item


@router.post("/{decision_id}/approve")
def approve(decision_id: str):
    appr = next((a for a in state.approvals if a["decision_id"] == decision_id), None)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    if appr["status"] != "pending":
        raise HTTPException(status_code=400, detail="Already resolved")

    appr["status"] = "approved"
    appr["resolved_at"] = datetime.now().isoformat()
    db.update_approval(decision_id, "approved", appr["resolved_at"])

    result = {}
    if appr["action"] == "generate_po" and appr.get("payload"):
        payload = appr["payload"]
        supplier = next(
            (s for s in state.suppliers if s["supplier_id"] == payload["supplier_id"]),
            None,
        )
        if supplier and supplier["availability"]:
            lead_days = supplier.get("catalog", {}).get(
                payload["sku_id"], {}
            ).get("lead_days", 7)
            po_id = f"PO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
            order = {
                "po_id": po_id,
                "supplier_id": payload["supplier_id"],
                "sku_id": payload["sku_id"],
                "quantity": payload["quantity"],
                "unit_price": payload["unit_price"],
                "total_amount": round(payload["unit_price"] * payload["quantity"], 2),
                "order_date": datetime.now().isoformat(),
                "expected_delivery": (
                    datetime.now() + timedelta(days=lead_days)
                ).isoformat(),
                "actual_delivery": None,
                "status": "approved",
                "reason": payload.get("reason", ""),
                "requested_by": "betsy-human-approved",
            }
            state.purchase_orders.append(order)
            result = {"po_id": po_id}

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "trigger": appr.get("sku_id", "approval"),
        "analysis": f"Human approved {appr['action']} — decision {decision_id[:8]}",
        "decision": "human_approved",
        "confidence": appr.get("confidence", 1.0),
        "metadata": {"decision_id": decision_id, "action": appr["action"], **result},
    }
    state.agent_log.append(log_entry)
    db.save_log_entry(log_entry)

    return {"status": "approved", **result}


@router.post("/{decision_id}/reject")
def reject(decision_id: str):
    appr = next((a for a in state.approvals if a["decision_id"] == decision_id), None)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    if appr["status"] != "pending":
        raise HTTPException(status_code=400, detail="Already resolved")

    appr["status"] = "rejected"
    appr["resolved_at"] = datetime.now().isoformat()
    db.update_approval(decision_id, "rejected", appr["resolved_at"])

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "trigger": appr.get("sku_id", "approval"),
        "analysis": f"Human declined {appr['action']} — decision {decision_id[:8]}",
        "decision": "human_rejected",
        "confidence": 1.0,
        "metadata": {"decision_id": decision_id, "action": appr["action"]},
    }
    state.agent_log.append(log_entry)
    db.save_log_entry(log_entry)

    return {"status": "rejected"}
