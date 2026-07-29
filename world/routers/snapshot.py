from fastapi import APIRouter

from world import db
from world.time_utils import day_to_iso

router = APIRouter(prefix="/api/snapshot", tags=["snapshot"])


@router.get("")
def get_snapshot():
    """All world data in one consistent read — the agent's brief can't be
    split across a tick boundary."""
    with db._lock:
        meta = db.get_meta()
        return {
            "clock": {
                "day": meta["day"],
                "date": day_to_iso(meta["day"]),
                "running": bool(meta["running"]),
            },
            "inventory": db.get_inventory(),
            "suppliers": db.get_suppliers(),
            "purchase_orders": db.get_purchase_orders(),
            "invoices": db.get_invoices(),
        }
