from fastapi import APIRouter

from world import db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset")
def reset_world():
    db.reset_to_seed()
    meta = db.get_meta()
    return {"status": "reset", "day": meta["day"], "seed": meta["seed"]}
