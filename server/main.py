from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from server.routers import inventory, suppliers, orders, invoices, scenarios, agent_log

DASHBOARD = Path(__file__).parent.parent / "dashboard" / "index.html"

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


@app.get("/", response_class=FileResponse, tags=["dashboard"])
def dashboard():
    return str(DASHBOARD)


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok", "docs": "/docs"}
