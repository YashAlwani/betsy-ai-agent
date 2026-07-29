"""Proxy to the world service — keeps the dashboard single-origin on Betsy."""
from fastapi import APIRouter, HTTPException

from shared import world_client

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("")
def get_inventory():
    return world_client.get_inventory()


@router.get("/{sku_id}")
def get_sku(sku_id: str):
    for item in world_client.get_inventory():
        if item["sku_id"] == sku_id:
            return item
    raise HTTPException(status_code=404, detail=f"SKU {sku_id} not found")
