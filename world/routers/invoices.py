import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from world import db
from world.time_utils import day_to_date, iso_to_day

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


def _find_duplicates(invoices: list) -> list:
    duplicates = []
    seen_pairs = set()
    for i, inv in enumerate(invoices):
        for j, other in enumerate(invoices):
            if i >= j:
                continue
            pair_key = tuple(sorted([inv["invoice_id"], other["invoice_id"]]))
            if pair_key in seen_pairs:
                continue
            if inv["supplier_id"] != other["supplier_id"]:
                continue
            if abs(inv["total_amount"] - other["total_amount"]) > 0.01:
                continue
            try:
                d1 = datetime.fromisoformat(inv["date"])
                d2 = datetime.fromisoformat(other["date"])
            except ValueError:
                continue
            days_apart = abs((d1 - d2).days)
            if days_apart <= 60:
                seen_pairs.add(pair_key)
                duplicates.append({
                    "invoice_1": inv["invoice_id"],
                    "invoice_2": other["invoice_id"],
                    "supplier_id": inv["supplier_id"],
                    "sku_id": inv["sku_id"],
                    "amount": inv["total_amount"],
                    "days_apart": days_apart,
                    "risk": "HIGH" if days_apart <= 30 else "MEDIUM",
                })
    return duplicates


class InvoiceCreate(BaseModel):
    supplier_id: str
    sku_id: str
    quantity: int
    unit_price: float
    total_amount: float
    date: str = ""
    po_reference: str = ""
    status: str = "received"
    invoice_id: str = ""


@router.get("")
def get_invoices():
    return db.get_invoices()


@router.get("/duplicates")
def get_duplicates():
    return _find_duplicates(db.get_invoices())


@router.get("/{invoice_id}")
def get_invoice(invoice_id: str):
    for inv in db.get_invoices():
        if inv["invoice_id"] == invoice_id:
            return inv
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")


@router.post("", status_code=201)
def submit_invoice(invoice: InvoiceCreate):
    data = invoice.model_dump()
    today = db.current_day()
    invoice_day = iso_to_day(data["date"]) if data["date"] else today
    if not data["invoice_id"]:
        stamp = day_to_date(invoice_day).strftime("%Y%m%d")
        data["invoice_id"] = f"INV-{stamp}-{str(uuid.uuid4())[:4].upper()}"
    with db._lock, db._conn() as c:
        c.execute(
            "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["invoice_id"], data["supplier_id"], data["sku_id"],
                data["quantity"], data["unit_price"], data["total_amount"],
                invoice_day, data["po_reference"], data["status"],
            ),
        )
    all_invoices = db.get_invoices()
    created = next(i for i in all_invoices if i["invoice_id"] == data["invoice_id"])
    flagged = [
        d for d in _find_duplicates(all_invoices)
        if data["invoice_id"] in (d["invoice_1"], d["invoice_2"])
    ]
    return {"invoice": created, "duplicate_flags": flagged}


@router.patch("/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status: str):
    valid = ["received", "paid", "disputed"]
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    with db._lock, db._conn() as c:
        cur = c.execute(
            "UPDATE invoices SET status = ? WHERE invoice_id = ?", (status, invoice_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return next(i for i in db.get_invoices() if i["invoice_id"] == invoice_id)
