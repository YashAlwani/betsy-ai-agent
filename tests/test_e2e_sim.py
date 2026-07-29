"""End-to-end simulation test — offline, no LLM.

Drives the world app in-process and exercises the full lifecycle:
stock drains over ticks -> a PO is placed -> the world delivers it and issues
an invoice -> Betsy's memory observes the delivery and updates her learned
supplier score. (The orchestra LLM layer is exercised separately; its rule
fallbacks make it optional here.)
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def world(tmp_path, monkeypatch):
    from world import db
    monkeypatch.setattr(db, "WORLD_DB_PATH", tmp_path / "world_e2e.db")
    from world.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def memory(tmp_path, monkeypatch):
    from server import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "betsy_e2e.db")
    db.init_db()
    from server import memory as mem
    return mem


def test_full_lifecycle(world, memory):
    # Day 0: bootstrap Betsy's memory from the world's seeded delivery history
    snap = world.get("/api/snapshot").json()
    updates = memory.observe_deliveries(snap["purchase_orders"], snap["suppliers"])
    assert len(updates) >= 8, "seeded history should bootstrap scores"
    bootstrapped = memory.get_scores()
    assert bootstrapped, "scores learned from history"

    # Place a PO with a fast supplier (as the agent would after a stockout finding)
    r = world.post("/api/purchase-orders", json={
        "supplier_id": "SUP-001",
        "sku_id": "SKU-003",
        "quantity": 400,
        "unit_price": 12.50,
        "reason": "e2e stockout replenishment",
        "requested_by": "betsy-orchestra",
    })
    assert r.status_code == 201
    po = r.json()
    assert po["status"] == "approved"

    # Let the world run: stock consumed daily, PO ships and arrives
    world.post("/api/clock/step", params={"days": 15})

    delivered = next(
        p for p in world.get("/api/purchase-orders").json() if p["po_id"] == po["po_id"]
    )
    assert delivered["status"] == "delivered"
    assert delivered["actual_delivery"] is not None

    # The supplier invoiced the delivery
    invoices = world.get("/api/invoices").json()
    assert any(i["po_reference"] == po["po_id"] for i in invoices)

    # Betsy observes the outcome and updates her learned score
    snap = world.get("/api/snapshot").json()
    updates = memory.observe_deliveries(snap["purchase_orders"], snap["suppliers"])
    assert any(u["po_id"] == po["po_id"] for u in updates)
    entry = memory.get_scores()["SUP-001"]
    assert entry["deliveries_observed"] > bootstrapped.get("SUP-001", {}).get("deliveries_observed", 0)

    # Learning is invisible to the world: its supplier payloads carry no score
    for sup in snap["suppliers"]:
        assert "reliability_score" not in sup


def test_stock_drains_until_replenished(world):
    start = {i["sku_id"]: i["current_stock"] for i in world.get("/api/inventory").json()}
    world.post("/api/clock/step", params={"days": 10})
    after = {i["sku_id"]: i["current_stock"] for i in world.get("/api/inventory").json()}
    drained = [sku for sku in start if after[sku] < start[sku]]
    assert len(drained) >= 8, "most SKUs should drain over 10 days"
