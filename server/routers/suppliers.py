"""World supplier facts merged with Betsy's learned reliability scores."""
import httpx
from fastapi import APIRouter, HTTPException, Query

from server import memory
from shared import world_client

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def get_suppliers():
    return memory.merge_scores_into_suppliers(world_client.get_suppliers())


@router.get("/scores")
def get_scores():
    """Raw view of what Betsy has learned so far."""
    return memory.get_scores()


@router.get("/{supplier_id}")
def get_supplier(supplier_id: str):
    for sup in memory.merge_scores_into_suppliers(world_client.get_suppliers()):
        if sup["supplier_id"] == supplier_id:
            return sup
    raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")


@router.get("/{supplier_id}/quote")
def get_quote(
    supplier_id: str,
    sku_id: str = Query(..., description="SKU to quote"),
    quantity: int = Query(1, ge=1, description="Quantity required"),
):
    try:
        return world_client.get_quote(supplier_id, sku_id, quantity)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code,
                            detail=exc.response.json().get("detail", str(exc)))
