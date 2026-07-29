"""World tick engine unit tests — offline, no LLM, temp world.db per test."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def world_db(tmp_path, monkeypatch):
    from world import db
    monkeypatch.setattr(db, "WORLD_DB_PATH", tmp_path / "world_test.db")
    db.init_db()
    return db


def _dump(db) -> dict:
    with db._conn() as c:
        return {
            table: [tuple(r) for r in c.execute(f"SELECT * FROM {table}").fetchall()]
            for table in ("sim_meta", "inventory", "suppliers", "supplier_catalog",
                          "purchase_orders", "invoices")
        }


def test_seeding_populates_world(world_db):
    assert len(world_db.get_inventory()) == 12
    assert len(world_db.get_suppliers()) == 6
    assert len(world_db.get_purchase_orders()) == 10
    assert len(world_db.get_invoices()) == 15
    assert world_db.current_day() == 0


def test_hidden_fields_never_serialized(world_db):
    for sup in world_db.get_suppliers():
        assert "true_reliability" not in sup
        assert "reliability_score" not in sup
    for po in world_db.get_purchase_orders():
        assert "arrival_day" not in po


def test_tick_consumes_stock_and_advances_day(world_db):
    from world import engine
    before = {i["sku_id"]: i["current_stock"] for i in world_db.get_inventory()}
    summary = engine.tick()
    assert summary["day"] == 1
    after = {i["sku_id"]: i["current_stock"] for i in world_db.get_inventory()}
    # Stock only moves down (no deliveries guaranteed on day 1 for every SKU),
    # and never below zero.
    consumed_any = False
    for sku, stock in after.items():
        assert stock >= 0
        if stock < before[sku]:
            consumed_any = True
    assert consumed_any


def test_open_po_gets_delivered_and_invoiced(world_db):
    from world import engine
    open_before = [po for po in world_db.get_purchase_orders()
                   if po["status"] not in ("delivered", "cancelled")]
    assert open_before, "seed data should contain an open PO"
    invoices_before = len(world_db.get_invoices())

    for _ in range(30):
        engine.tick()

    pos = {po["po_id"]: po for po in world_db.get_purchase_orders()}
    for po in open_before:
        updated = pos[po["po_id"]]
        assert updated["status"] == "delivered"
        assert updated["actual_delivery"] is not None
    assert len(world_db.get_invoices()) > invoices_before


def test_determinism_same_seed_same_history(world_db):
    from world import engine
    for _ in range(15):
        engine.tick()
    first = _dump(world_db)

    world_db.reset_to_seed()
    for _ in range(15):
        engine.tick()
    second = _dump(world_db)

    for table in ("sim_meta", "inventory", "suppliers", "supplier_catalog"):
        assert first[table] == second[table], f"{table} diverged"
    # Tick-created invoices carry uuid-based ids, so compare the deterministic
    # columns (supplier, sku, qty, amounts, day) rather than full rows.
    def stable_invoices(rows):
        return sorted((r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows)
    assert len(first["purchase_orders"]) == len(second["purchase_orders"])
    assert stable_invoices(first["invoices"]) == stable_invoices(second["invoices"])


def test_po_creation_draws_hidden_arrival(world_db):
    with world_db._lock, world_db._conn() as c:
        row = c.execute(
            "SELECT arrival_day, expected_day FROM purchase_orders WHERE status != 'delivered'"
        ).fetchone()
    assert row is not None
    assert row["arrival_day"] >= 1
