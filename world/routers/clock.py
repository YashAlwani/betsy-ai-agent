from fastapi import APIRouter, HTTPException, Query

from world import db, engine
from world.time_utils import day_to_iso

router = APIRouter(prefix="/api/clock", tags=["clock"])


def _clock_state() -> dict:
    meta = db.get_meta()
    return {
        "day": meta["day"],
        "date": day_to_iso(meta["day"]),
        "running": bool(meta["running"]),
        "tick_seconds": meta["tick_seconds"],
        "seed": meta["seed"],
    }


@router.get("")
def get_clock():
    return _clock_state()


@router.post("/play")
def play():
    db.set_meta(running=1)
    return _clock_state()


@router.post("/pause")
def pause():
    db.set_meta(running=0)
    return _clock_state()


@router.post("/step")
def step(days: int = Query(1, ge=1, le=365)):
    if db.get_meta()["running"]:
        raise HTTPException(status_code=409, detail="Pause the clock before stepping")
    summaries = [engine.tick() for _ in range(days)]
    return {"stepped": days, "clock": _clock_state(), "last_tick": summaries[-1]}


@router.post("/speed")
def speed(tick_seconds: float = Query(..., gt=0.1, le=600)):
    db.set_meta(tick_seconds=tick_seconds)
    return _clock_state()
