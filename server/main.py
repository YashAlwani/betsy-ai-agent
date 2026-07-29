import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server import agent_loop, db
from server.routers import (
    agent_log,
    approvals,
    inventory,
    invoices,
    notifications,
    orders,
    sim,
    stats,
    suppliers,
)
from server.scheduler_instance import scheduler
from shared import world_client

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"
BETSY     = Path(__file__).parent.parent / "dashboard" / "betsy.html"

logger = logging.getLogger("betsy.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not world_client.is_up():
        logger.warning(
            "World service not reachable at %s — start it with: python run_world.py",
            world_client.WORLD_BASE,
        )
    scheduler.add_job(
        agent_loop.poll_once,
        trigger="interval",
        seconds=agent_loop.POLL_SECONDS,
        id="betsy_agent_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Agent loop started — polling world clock every %.0fs, runs every %d sim day(s)",
        agent_loop.POLL_SECONDS, agent_loop.AGENT_RUN_EVERY_DAYS,
    )
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Betsy",
    description="Autonomous procurement agent: lifecycle loop, approvals, "
                "supplier learning, notifications. Talks to the world (simulated ERP) "
                "through the WorldClient adapter.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(orders.router)
app.include_router(invoices.router)
app.include_router(sim.router)
app.include_router(agent_log.router)
app.include_router(approvals.router)
app.include_router(stats.router)
app.include_router(notifications.router)


@app.get("/", response_class=FileResponse, tags=["dashboard"])
def dashboard():
    return str(DASHBOARD)


@app.get("/betsy", response_class=FileResponse, tags=["dashboard"])
def betsy_dashboard():
    return str(BETSY)


@app.get("/api/agent-status", tags=["agent"])
def agent_status():
    return agent_loop.status()


@app.post("/api/run-agent", tags=["agent"])
def run_agent(background_tasks: BackgroundTasks, mode: str = "orchestra"):
    """Manual trigger (in addition to the automatic clock-driven loop)."""
    def _run():
        if mode == "pipeline":
            from pipeline.run import run_full
        else:
            from orchestra.run import run_full
        run_full()
    background_tasks.add_task(_run)
    return {"status": "started", "mode": mode}


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok", "docs": "/docs", "world_up": world_client.is_up()}
