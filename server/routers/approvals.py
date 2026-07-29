import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException

from server import db, notifier
from shared import world_client

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("")
def get_approvals():
    return db.load_pending_approvals()


@router.post("", status_code=201)
def queue_approval(item: dict):
    if "decision_id" not in item:
        item["decision_id"] = str(uuid.uuid4())
    if "status" not in item:
        item["status"] = "pending"
    if "created_at" not in item:
        item["created_at"] = datetime.now().isoformat()
    db.save_approval(item)

    # Fire desktop + email notification for the queued item.
    # All action types (generate_po, flag_duplicate, flag_for_approval, escalate)
    # use the same approval notification; the action label differentiates them.
    notifier.notify_approval_required(item)

    return item


@router.post("/{decision_id}/approve")
def approve(decision_id: str):
    appr = db.get_approval(decision_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    if appr["status"] != "pending":
        raise HTTPException(status_code=400, detail="Already resolved")

    resolved_at = datetime.now().isoformat()
    db.update_approval(decision_id, "approved", resolved_at)

    result = {}
    payload = appr.get("payload") or {}

    if appr["action"] == "generate_po" and payload:
        try:
            order = world_client.create_po({
                "supplier_id": payload["supplier_id"],
                "sku_id": payload["sku_id"],
                "quantity": payload["quantity"],
                "unit_price": payload["unit_price"],
                "reason": payload.get("reason", ""),
                "requested_by": "betsy-human-approved",
            })
            result = {"po_id": order["po_id"]}
        except (httpx.HTTPError, KeyError) as exc:
            result = {"po_error": str(exc)}

    elif appr["action"] == "flag_duplicate" and payload.get("invoice_id"):
        # Approving a duplicate flag = confirming the dispute in the world
        try:
            world_client.patch_invoice_status(payload["invoice_id"], "disputed")
            result = {"disputed_invoice": payload["invoice_id"]}
        except httpx.HTTPError as exc:
            result = {"dispute_error": str(exc)}

    db.save_log_entry({
        "timestamp": resolved_at,
        "trigger": appr.get("sku_id") or "approval",
        "analysis": f"Human approved {appr['action']} — decision {decision_id[:8]}",
        "decision": "human_approved",
        "confidence": appr.get("confidence", 1.0),
        "metadata": {"decision_id": decision_id, "action": appr["action"], **result},
    })

    return {"status": "approved", **result}


@router.post("/{decision_id}/reject")
def reject(decision_id: str):
    appr = db.get_approval(decision_id)
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found")
    if appr["status"] != "pending":
        raise HTTPException(status_code=400, detail="Already resolved")

    resolved_at = datetime.now().isoformat()
    db.update_approval(decision_id, "rejected", resolved_at)

    db.save_log_entry({
        "timestamp": resolved_at,
        "trigger": appr.get("sku_id") or "approval",
        "analysis": f"Human declined {appr['action']} — decision {decision_id[:8]}",
        "decision": "human_rejected",
        "confidence": 1.0,
        "metadata": {"decision_id": decision_id, "action": appr["action"]},
    })

    return {"status": "rejected"}
