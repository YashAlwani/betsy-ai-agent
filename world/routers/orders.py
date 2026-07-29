import random
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from world import db
from world.time_utils import day_to_date, iso_to_day

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
    return db.get_purchase_orders()


@router.get("/{po_id}")
def get_order(po_id: str):
    for order in db.get_purchase_orders():
        if order["po_id"] == po_id:
            return order
    raise HTTPException(status_code=404, detail=f"PO {po_id} not found")


@router.post("", status_code=201)
def create_order(po: POCreate):
    """Create a committed PO. Pending decisions live in Betsy's approvals queue,
    so anything reaching the world is already approved."""
    with db._lock, db._conn() as c:
        sup = c.execute(
            "SELECT * FROM suppliers WHERE supplier_id = ?", (po.supplier_id,)
        ).fetchone()
        if not sup:
            raise HTTPException(status_code=404, detail=f"Supplier {po.supplier_id} not found")
        if not sup["availability"]:
            raise HTTPException(status_code=503, detail=f"Supplier {sup['name']} is unavailable")

        cat = c.execute(
            "SELECT lead_days FROM supplier_catalog WHERE supplier_id = ? AND sku_id = ?",
            (po.supplier_id, po.sku_id),
        ).fetchone()
        lead_days = cat["lead_days"] if cat else 7

        day = c.execute("SELECT day, seed FROM sim_meta WHERE id = 1").fetchone()
        today, seed = day["day"], day["seed"]

        po_id = f"PO-{day_to_date(today).strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        expected_day = today + lead_days
        rng = random.Random(f"{seed}:po:{po_id}")
        arrival_day = db.draw_arrival_day(rng, expected_day, sup["true_reliability"])

        c.execute(
            "INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                po_id, po.supplier_id, po.sku_id, po.quantity, po.unit_price,
                round(po.unit_price * po.quantity, 2), today, expected_day,
                arrival_day, None, "approved", po.reason, po.requested_by,
            ),
        )
        row = c.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,)).fetchone()
    return db.serialize_po(row)


@router.patch("/{po_id}/status")
def update_order_status(po_id: str, status: str, actual_delivery: str = None):
    """Admin/testing hook. Delivery normally happens via the tick engine.
    actual_delivery (ISO date) lets evidence scripts force a specific lateness."""
    valid = ["approved", "in_transit", "delivered", "cancelled"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    with db._lock, db._conn() as c:
        row = c.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"PO {po_id} not found")
        if status == "delivered":
            if actual_delivery:
                actual_day = iso_to_day(actual_delivery)
            else:
                actual_day = c.execute("SELECT day FROM sim_meta WHERE id = 1").fetchone()["day"]
            c.execute(
                "UPDATE purchase_orders SET status = ?, actual_day = ? WHERE po_id = ?",
                (status, actual_day, po_id),
            )
        else:
            c.execute("UPDATE purchase_orders SET status = ? WHERE po_id = ?", (status, po_id))
        row = c.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,)).fetchone()
    return db.serialize_po(row)
