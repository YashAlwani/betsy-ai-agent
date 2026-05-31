from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server.routers import inventory, suppliers, orders, invoices, scenarios, agent_log, approvals

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"
BETSY     = Path(__file__).parent.parent / "dashboard" / "betsy.html"

app = FastAPI(
    title="Betsy Mock Server",
    description="Mock procurement API for the Betsy autonomous agent",
    version="0.1.0",
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
