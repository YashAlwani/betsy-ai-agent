import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server import db
from server.state import state

EMA_ALPHA = 0.2  # new delivery counts 20%, history 80%

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


class POCreate(BaseModel):
    supplier_id: str
    sku_id: str
    quantity: int
    unit_price: float
    reason: str = ""
    requested_by: str = "betsy-agent"


@router.get("")
def get_orders():
    return state.purchase_orders


@router.get("/{po_id}")
def get_order(po_id: str):
    for order in state.purchase_orders:
        if order["po_id"] == po_id:
            return order
    raise HTTPException(status_code=404, detail=f"PO {po_id} not found")


@router.post("", status_code=201)
def create_order(po: POCreate):
    supplier = next((s for s in state.suppliers if s["supplier_id"] == po.supplier_id), None)
    if not supplier:
        raise HTTPException(status_code=404, detail=f"Supplier {po.supplier_id} not found")
    if not supplier["availability"]:
        raise HTTPException(status_code=503, detail=f"Supplier {supplier['name']} is unavailable")

    lead_days = supplier.get("catalog", {}).get(po.sku_id, {}).get("lead_days", 7)
    po_id = f"PO-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

    order = {
        "po_id": po_id,
        "supplier_id": po.supplier_id,
        "sku_id": po.sku_id,
        "quantity": po.quantity,
        "unit_price": po.unit_price,
        "total_amount": round(po.unit_price * po.quantity, 2),
        "order_date": datetime.now().isoformat(),
        "expected_delivery": (datetime.now() + timedelta(days=lead_days)).isoformat(),
        "actual_delivery": None,
        "status": "pending_approval",
        "reason": po.reason,
        "requested_by": po.requested_by,
    }
    state.purchase_orders.append(order)
    return order


@router.patch("/{po_id}/status")
def update_order_status(po_id: str, status: str, actual_delivery: str = None):
    valid = ["pending_approval", "approved", "in_transit", "delivered", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    for order in state.purchase_orders:
        if order["po_id"] == po_id:
            order["status"] = status
            if status == "delivered":
                order["actual_delivery"] = actual_delivery or datetime.now().isoformat()
                _apply_ema(order)
            return order
    raise HTTPException(status_code=404, detail=f"PO {po_id} not found")


def _apply_ema(order: dict) -> None:
    supplier = next(
        (s for s in state.suppliers if s["supplier_id"] == order["supplier_id"]), None
    )
    if not supplier:
        return

    try:
        expected = datetime.fromisoformat(order["expected_delivery"][:19])
        actual   = datetime.fromisoformat(order["actual_delivery"][:19])
        lateness = max(0, (actual - expected).days)
    except Exception:
        return

    performance = max(0.0, 1.0 - lateness * 0.1)
    old_score   = supplier["reliability_score"]
    new_score   = round(
        min(1.0, max(0.0, EMA_ALPHA * performance + (1 - EMA_ALPHA) * old_score)), 4
    )
    supplier["reliability_score"] = new_score

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "trigger":   "ema_score_update",
        "analysis":  (
            f"{supplier['name']} delivered PO {order['po_id']} "
            f"{'on time' if lateness == 0 else f'{lateness}d late'} — "
            f"score {old_score:.4f} → {new_score:.4f}"
        ),
        "decision":  "score_updated",
        "confidence": performance,
        "metadata": {
            "supplier_id":  supplier["supplier_id"],
            "supplier_name": supplier["name"],
            "po_id":        order["po_id"],
            "lateness_days": lateness,
            "performance":  round(performance, 4),
            "old_score":    old_score,
            "new_score":    new_score,
            "ema_alpha":    EMA_ALPHA,
        },
    }
    state.agent_log.append(log_entry)
    db.save_log_entry(log_entry)
