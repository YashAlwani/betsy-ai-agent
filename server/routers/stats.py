from fastapi import APIRouter

from server import db
from server.scheduler_instance import scheduler
from shared import world_client

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats():
    log       = db.load_log_entries()
    pending   = db.load_pending_approvals()

    auto      = [e for e in log
                 if e.get("decision") not in ("human_approved", "human_rejected", "score_updated")
                 and not e.get("metadata", {}).get("requires_human")]
    human     = [e for e in log if e.get("decision") in ("human_approved", "human_rejected")]
    ema_updates = [e for e in log if e.get("decision") == "score_updated"]

    total        = len(log)
    auto_count   = len(auto)
    human_count  = len(human)
    queue_value  = sum(a.get("po_total") or 0 for a in pending)

    last_run_entry = next(
        (e for e in reversed(log) if e.get("trigger") in ("orchestra_run", "pipeline_run")), None
    )

    cursor = db.get_agent_cursor()
    try:
        sim_day = world_client.get_clock().get("day")
    except Exception:
        sim_day = None

    return {
        "decisions_total":   total,
        "decisions_auto":    auto_count,
        "decisions_human":   human_count,
        "ema_updates":       len(ema_updates),
        "auto_rate_pct":     round(auto_count / total * 100, 1) if total else 0.0,
        "pending_approvals": len(pending),
        "queue_value_eur":   round(queue_value, 2),
        "last_run":          last_run_entry["timestamp"] if last_run_entry else None,
        "last_run_day":      cursor["last_run_day"],
        "sim_day":           sim_day,
        "scheduler_active":  scheduler.running,
        "next_run":          None,
    }
