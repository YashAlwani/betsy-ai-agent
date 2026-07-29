"""Proxy to the world service. Invoices are issued by the world's tick engine;
Betsy can dispute them (duplicate / amount errors) via PATCH."""
import httpx
from fastapi import APIRouter, HTTPException

from shared import world_client

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("")
def get_invoices():
    return world_client.get_invoices()


@router.get("/duplicates")
def get_duplicates():
    return httpx.get(
        f"{world_client.WORLD_BASE}/api/invoices/duplicates", timeout=world_client.TIMEOUT
    ).json()


@router.get("/{invoice_id}")
def get_invoice(invoice_id: str):
    for inv in world_client.get_invoices():
        if inv["invoice_id"] == invoice_id:
            return inv
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")


@router.patch("/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status: str):
    try:
        return world_client.patch_invoice_status(invoice_id, status)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code,
                            detail=exc.response.json().get("detail", str(exc)))
