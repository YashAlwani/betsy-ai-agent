from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from server import db
from server.state import state

router = APIRouter(prefix="/api/agent-log", tags=["agent-log"])


class LogEntry(BaseModel):
    trigger: str
    analysis: str
    decision: str
    confidence: float = 0.0
    metadata: dict = {}


@router.get("")
def get_log():
    return state.agent_log


@router.delete("")
def clear_log():
    state.agent_log.clear()
    db.clear_log()
    return {"status": "cleared"}


@router.post("", status_code=201)
def add_log_entry(entry: LogEntry):
    record = {
        "timestamp": datetime.now().isoformat(),
        "trigger": entry.trigger,
        "analysis": entry.analysis,
        "decision": entry.decision,
        "confidence": entry.confidence,
        "metadata": entry.metadata,
    }
    state.agent_log.append(record)
    db.save_log_entry(record)
    return record
