"""Background clock: ticks the engine while sim_meta.running is set."""
import asyncio
import logging

from world import db, engine

logger = logging.getLogger("world.runner")

_task: asyncio.Task | None = None


async def _loop() -> None:
    while True:
        meta = db.get_meta()
        if meta["running"]:
            try:
                summary = await asyncio.to_thread(engine.tick)
                logger.info("tick -> day %s", summary["day"])
            except Exception as exc:
                logger.error("tick failed: %s", exc)
            await asyncio.sleep(max(0.25, meta["tick_seconds"]))
        else:
            await asyncio.sleep(0.5)


def start() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())


def stop() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None
