"""Betsy's autonomous trigger: poll the world clock and run the lifecycle.

The world stays passive (like a real ERP); Betsy polls its clock every few
real seconds. When at least AGENT_RUN_EVERY_DAYS sim days have passed since
the last run, one cycle executes:

  1. observe deliveries -> update learned supplier scores (EMA)
  2. run the orchestra (detect -> decide -> act -> audit)

A non-reentrant lock guards the cycle (an Ollama-backed run can take 30-60s
while the world keeps ticking), and multi-day jumps coalesce into one run.
"""
import logging
import os
import threading

from server import db, memory
from shared import world_client

logger = logging.getLogger("betsy.agent_loop")

AGENT_RUN_EVERY_DAYS = int(os.getenv("AGENT_RUN_EVERY_DAYS", "1"))
POLL_SECONDS = float(os.getenv("AGENT_POLL_SECONDS", "3"))

_run_lock = threading.Lock()
_current_run_day: int | None = None   # set while a run is in flight (dashboard "thinking" state)


def status() -> dict:
    return {
        "running": _run_lock.locked(),
        "run_day": _current_run_day,
        "cadence_days": AGENT_RUN_EVERY_DAYS,
        "last_run_day": db.get_agent_cursor()["last_run_day"],
    }


def poll_once() -> None:
    """Scheduler entrypoint: check the clock, run the agent if a sim day is due."""
    global _current_run_day

    if not _run_lock.acquire(blocking=False):
        return  # a run is already in flight
    try:
        try:
            clock = world_client.get_clock()
        except Exception:
            return  # world unreachable; try again next poll
        day = clock["day"]
        cursor = db.get_agent_cursor()

        if cursor["last_run_day"] < 0:
            # First contact with this world: learn from seeded history,
            # then run on the next due day.
            _observe(day)
            db.set_agent_cursor(day)
            return

        if day < cursor["last_run_day"] + AGENT_RUN_EVERY_DAYS:
            return

        _current_run_day = day
        logger.info("Agent cycle for sim day %s", day)
        _observe(day)
        _run_orchestra()
        db.set_agent_cursor(day)
    finally:
        _current_run_day = None
        _run_lock.release()


def _observe(day: int) -> None:
    try:
        snapshot = world_client.get_snapshot()
        updates = memory.observe_deliveries(
            snapshot["purchase_orders"], snapshot["suppliers"]
        )
        if updates:
            logger.info("EMA updates: %s", [(u["supplier_id"], u["new_score"]) for u in updates])
    except Exception as exc:
        logger.error("observe_deliveries failed: %s", exc)


def _run_orchestra() -> None:
    try:
        from orchestra.run import run_full
        run_full()
    except Exception as exc:
        logger.error("orchestra run failed: %s", exc)
