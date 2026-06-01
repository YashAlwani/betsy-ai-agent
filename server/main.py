import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server.routers import inventory, suppliers, orders, invoices, scenarios, agent_log, approvals, stats
from server.scheduler_instance import scheduler

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"
BETSY     = Path(__file__).parent.parent / "dashboard" / "betsy.html"

logger = logging.getLogger("betsy.scheduler")


def _scheduled_run() -> None:
    try:
        from pipeline.run import run_full
        run_full(scenario=None)
    except Exception as exc:
        logger.error("Scheduled run failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    interval = int(os.getenv("AGENT_INTERVAL_MINUTES", "30"))
    scheduler.add_job(
        _scheduled_run,
        trigger="interval",
        minutes=interval,
        id="betsy_auto_run",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — auto-run every %d min", interval)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Betsy Mock Server",
    description="Mock procurement API for the Betsy autonomous agent",
    version="0.1.0",
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
app.include_router(scenarios.router)
app.include_router(agent_log.router)
app.include_router(approvals.router)
app.include_router(stats.router)


@app.get("/", response_class=FileResponse, tags=["dashboard"])
def dashboard():
    return str(DASHBOARD)


@app.get("/betsy", response_class=FileResponse, tags=["dashboard"])
def betsy_dashboard():
    return str(BETSY)


@app.post("/api/run-agent", tags=["agent"])
def run_agent(background_tasks: BackgroundTasks, scenario: str = "", mode: str = "pipeline"):
    def _run():
        if mode == "orchestra":
            from orchestra.run import run_full
        else:
            from pipeline.run import run_full
        run_full(scenario=scenario or None)
    background_tasks.add_task(_run)
    return {"status": "started", "mode": mode, "scenario": scenario or "normal"}


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok", "docs": "/docs"}
