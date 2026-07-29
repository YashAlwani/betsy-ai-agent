"""Event injection and scenario script tests — offline, via the world FastAPI app."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from world import db
    monkeypatch.setattr(db, "WORLD_DB_PATH", tmp_path / "world_test.db")
    from world.main import app
    with TestClient(app) as c:
        yield c


def test_inject_event_applies_on_next_tick(client):
    r = client.post("/api/events", json={
        "type": "stock_set",
        "payload": {"sku_id": "SKU-003", "current_stock": 45},
    })
    assert r.status_code == 201

    client.post("/api/clock/step", params={"days": 1})
    sku = client.get("/api/inventory/SKU-003").json()
    # stock_set applies before consumption that day, so stock is 45 minus one day's usage
    assert sku["current_stock"] <= 45


def test_unknown_event_type_rejected(client):
    r = client.post("/api/events", json={"type": "meteor_strike", "payload": {}})
    assert r.status_code == 400


def test_script_injection_offsets_from_current_day(client):
    client.post("/api/clock/step", params={"days": 3})
    r = client.post("/api/events/script/supplier_oos")
    assert r.status_code == 201
    body = r.json()
    assert body["queued_events"] == 2
    assert body["from_day"] == 4

    client.post("/api/clock/step", params={"days": 1})
    sup = client.get("/api/suppliers/SUP-004").json()
    assert sup["availability"] is False


def test_outage_auto_restores(client):
    client.post("/api/events", json={
        "type": "supplier_outage",
        "payload": {"supplier_id": "SUP-001", "duration_days": 2},
    })
    client.post("/api/clock/step", params={"days": 1})
    assert client.get("/api/suppliers/SUP-001").json()["availability"] is False
    client.post("/api/clock/step", params={"days": 3})
    assert client.get("/api/suppliers/SUP-001").json()["availability"] is True


def test_duplicate_invoice_event_visible_in_duplicates(client):
    r = client.post("/api/events", json={
        "type": "duplicate_invoice",
        "payload": {"supplier_id": "SUP-006"},
    })
    assert r.status_code == 201
    client.post("/api/clock/step", params={"days": 1})
    dupes = client.get("/api/invoices/duplicates").json()
    assert any(d["supplier_id"] == "SUP-006" for d in dupes)


def test_step_blocked_while_running(client):
    client.post("/api/clock/play")
    r = client.post("/api/clock/step", params={"days": 1})
    assert r.status_code == 409
    client.post("/api/clock/pause")


def test_reset_returns_to_day_zero(client):
    client.post("/api/clock/step", params={"days": 5})
    assert client.get("/api/clock").json()["day"] == 5
    client.post("/api/admin/reset")
    assert client.get("/api/clock").json()["day"] == 0
