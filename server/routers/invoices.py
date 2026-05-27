import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from server.state import state

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
    date: str
    po_reference: str = ""
    status: str = "received"
    invoice_id: str = ""


@router.get("")
def get_invoices():
    return state.invoices


@router.get("/duplicates")
def get_duplicates():
    return _find_duplicates(state.invoices)


@router.get("/{invoice_id}")
def get_invoice(invoice_id: str):
    for inv in state.invoices:
        if inv["invoice_id"] == invoice_id:
            return inv
    return {"error": f"Invoice {invoice_id} not found"}


@router.post("", status_code=201)
def submit_invoice(invoice: InvoiceCreate):
    data = invoice.model_dump()
    if not data["invoice_id"]:
        data["invoice_id"] = f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    state.invoices.append(data)
    duplicates = _find_duplicates(state.invoices)
    flagged = [
        d for d in duplicates
        if data["invoice_id"] in (d["invoice_1"], d["invoice_2"])
    ]
    return {"invoice": data, "duplicate_flags": flagged}
