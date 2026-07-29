import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from world import db, engine
from world.config import SCENARIOS

router = APIRouter(prefix="/api/events", tags=["events"])

VALID_TYPES = sorted(engine._EVENT_HANDLERS)


class EventCreate(BaseModel):
    type: str
    payload: dict = {}
    day: int | None = None   # omitted -> applies on the next tick


@router.get("")
def list_events(since: int = 0, limit: int = 100):
    """Events with id > since, oldest first (tick summaries included)."""
    with db._conn() as c:
        rows = c.execute(
            "SELECT * FROM events WHERE id > ? ORDER BY id DESC LIMIT ?",
            (since, limit),
        ).fetchall()
    return [db.serialize_event(r) for r in reversed(rows)]


@router.get("/scripts")
def list_scripts():
    scripts = []
    if SCENARIOS.exists():
        for path in sorted(SCENARIOS.glob("*.json")):
            data = json.loads(path.read_text())
            scripts.append({"name": path.stem, "description": data.get("description", "")})
    return scripts


@router.post("", status_code=201)
def inject_event(event: EventCreate):
    if event.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown type. Valid: {VALID_TYPES}")
    day = event.day if event.day is not None else db.current_day() + 1
    with db._lock, db._conn() as c:
        cur = c.execute(
            "INSERT INTO events (day, type, payload, source) VALUES (?, ?, ?, 'injected')",
            (day, event.type, json.dumps(event.payload)),
        )
        row = c.execute("SELECT * FROM events WHERE id = ?", (cur.lastrowid,)).fetchone()
    return db.serialize_event(row)


@router.post("/script/{name}", status_code=201)
def inject_script(name: str):
    """Queue a scenario script's events relative to the current sim day."""
    path = SCENARIOS / f"{name}.json"
    if not path.exists():
        available = [p.stem for p in SCENARIOS.glob("*.json")]
        raise HTTPException(status_code=404, detail=f"Unknown script '{name}'. Available: {available}")
    script = json.loads(path.read_text())
    base_day = db.current_day()
    queued = []
    with db._lock, db._conn() as c:
        for ev in script.get("events", []):
            if ev["type"] not in VALID_TYPES:
                continue
            day = base_day + max(1, int(ev.get("day_offset", 0)) + 1)
            cur = c.execute(
                "INSERT INTO events (day, type, payload, source) VALUES (?, ?, ?, 'script')",
                (day, ev["type"], json.dumps(ev.get("payload", {}))),
            )
            queued.append(cur.lastrowid)
    return {
        "script": name,
        "description": script.get("description", ""),
        "queued_events": len(queued),
        "from_day": base_day + 1,
    }
