from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from world import db, runner
from world.routers import admin, clock, events, inventory, invoices, orders, snapshot, suppliers


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    runner.start()
    yield
    runner.stop()


app = FastAPI(
    title="Betsy World (Simulated ERP)",
    description="Standalone simulated procurement environment: inventory, suppliers, "
                "purchase orders, invoices, and a controllable sim clock.",
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
app.include_router(clock.router)
app.include_router(events.router)
app.include_router(snapshot.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", tags=["root"])
def health():
    return {"status": "ok", "service": "world", "day": db.current_day()}
