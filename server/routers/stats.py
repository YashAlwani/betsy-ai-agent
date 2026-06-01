from fastapi import APIRouter

from server.scheduler_instance import scheduler
from server.state import state

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats():
    log       = state.agent_log
    approvals = state.approvals

    pending   = [a for a in approvals if a["status"] == "pending"]
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
        (e for e in reversed(log) if e.get("trigger") == "pipeline_run"), None
    )

    job      = scheduler.get_job("betsy_auto_run") if scheduler.running else None
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None

    return {
        "decisions_total":   total,
        "decisions_auto":    auto_count,
        "decisions_human":   human_count,
        "ema_updates":       len(ema_updates),
        "auto_rate_pct":     round(auto_count / total * 100, 1) if total else 0.0,
        "pending_approvals": len(pending),
        "queue_value_eur":   round(queue_value, 2),
        "last_run":          last_run_entry["timestamp"] if last_run_entry else None,
        "scheduler_active":  scheduler.running,
        "next_run":          next_run,
    }
