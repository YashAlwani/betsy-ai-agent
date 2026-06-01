from fastapi import APIRouter, HTTPException, Query

from server.state import state

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("")
def get_suppliers():
    return state.suppliers


@router.get("/{supplier_id}")
def get_supplier(supplier_id: str):
    for sup in state.suppliers:
        if sup["supplier_id"] == supplier_id:
            return sup
    raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")


@router.patch("/{supplier_id}/score")
def update_supplier_score(supplier_id: str, reliability_score: float):
    for sup in state.suppliers:
        if sup["supplier_id"] == supplier_id:
            old = sup["reliability_score"]
            sup["reliability_score"] = round(max(0.0, min(1.0, reliability_score)), 4)
            return {"supplier_id": supplier_id, "name": sup["name"],
                    "old_score": old, "new_score": sup["reliability_score"]}
    raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")


@router.get("/{supplier_id}/quote")
def get_quote(
    supplier_id: str,
    sku_id: str = Query(..., description="SKU to quote"),
    quantity: int = Query(1, ge=1, description="Quantity required"),
):
    for sup in state.suppliers:
        if sup["supplier_id"] != supplier_id:
            continue
        if not sup["availability"]:
            raise HTTPException(status_code=503, detail=f"Supplier {sup['name']} is currently unavailable")
        catalog = sup.get("catalog", {})
        if sku_id not in catalog:
            raise HTTPException(status_code=404, detail=f"SKU {sku_id} not in {sup['name']} catalog")
        entry = catalog[sku_id]
        return {
            "supplier_id": supplier_id,
            "supplier_name": sup["name"],
            "sku_id": sku_id,
            "quantity": quantity,
            "unit_price": entry["unit_price"],
            "lead_days": entry["lead_days"],
            "total_price": round(entry["unit_price"] * quantity, 2),
            "available": sup["availability"],
        }
    raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found")
