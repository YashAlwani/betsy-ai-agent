import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.state import state

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
def update_order_status(po_id: str, status: str):
    valid = ["pending_approval", "approved", "in_transit", "delivered", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    for order in state.purchase_orders:
        if order["po_id"] == po_id:
            order["status"] = status
            return order
    raise HTTPException(status_code=404, detail=f"PO {po_id} not found")
