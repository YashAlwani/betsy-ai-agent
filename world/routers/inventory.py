from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from world import db

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class StockUpdate(BaseModel):
    current_stock: int


@router.get("")
def get_inventory():
    return db.get_inventory()


@router.get("/{sku_id}")
def get_sku(sku_id: str):
    for item in db.get_inventory():
        if item["sku_id"] == sku_id:
            return item
    raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")


@router.patch("/{sku_id}")
def update_stock(sku_id: str, update: StockUpdate):
    with db._lock, db._conn() as c:
        cur = c.execute(
            "UPDATE inventory SET current_stock = ? WHERE sku_id = ?",
            (update.current_stock, sku_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
    return next(i for i in db.get_inventory() if i["sku_id"] == sku_id)
