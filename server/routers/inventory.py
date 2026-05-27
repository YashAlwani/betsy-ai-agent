from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.state import state

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class StockUpdate(BaseModel):
    current_stock: int


@router.get("")
def get_inventory():
    return state.inventory


@router.get("/{sku_id}")
def get_sku(sku_id: str):
    for item in state.inventory:
        if item["sku_id"] == sku_id:
            return item
    raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")


@router.patch("/{sku_id}")
def update_stock(sku_id: str, update: StockUpdate):
    for item in state.inventory:
        if item["sku_id"] == sku_id:
            item["current_stock"] = update.current_stock
            return item
    raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
