"""Proxy for the world's sim controls (clock, events, scripts, reset) so the
dashboard stays single-origin on Betsy."""
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared import world_client

router = APIRouter(prefix="/api/sim", tags=["sim"])


class EventCreate(BaseModel):
    type: str
    payload: dict = {}
    day: int | None = None


def _forward(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.json().get("detail", str(exc))
        raise HTTPException(status_code=exc.response.status_code, detail=detail)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="World service unreachable")


@router.get("/clock")
def get_clock():
    return _forward(world_client.get_clock)


@router.post("/clock/play")
def play():
    return _forward(world_client.play)


@router.post("/clock/pause")
def pause():
    return _forward(world_client.pause)


@router.post("/clock/step")
def step(days: int = 1):
    return _forward(world_client.step, days)


@router.post("/clock/speed")
def speed(tick_seconds: float):
    return _forward(world_client.set_speed, tick_seconds)


@router.get("/events")
def events(since: int = 0, limit: int = 100):
    return _forward(world_client.get_events, since, limit)


@router.get("/scripts")
def scripts():
    return _forward(world_client.list_scripts)


@router.post("/events")
def inject_event(event: EventCreate):
    return _forward(world_client.inject_event, event.model_dump())


@router.post("/scripts/{name}")
def inject_script(name: str):
    return _forward(world_client.inject_script, name)


@router.post("/reset")
def reset():
    return _forward(world_client.reset_world)
