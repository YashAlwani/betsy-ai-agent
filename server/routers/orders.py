"""Proxy to the world service. PO lifecycle (delivery, invoicing) is owned by
the world's tick engine; Betsy learns from outcomes via server.memory."""
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import world_client

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
    return world_client.get_purchase_orders()


@router.get("/{po_id}")
def get_order(po_id: str):
    for order in world_client.get_purchase_orders():
        if order["po_id"] == po_id:
            return order
    raise HTTPException(status_code=404, detail=f"PO {po_id} not found")


@router.post("", status_code=201)
def create_order(po: POCreate):
    try:
        return world_client.create_po(po.model_dump())
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code,
                            detail=exc.response.json().get("detail", str(exc)))
