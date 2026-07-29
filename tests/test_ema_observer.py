"""EMA observer tests — Betsy's learned supplier memory, offline with a temp betsy.db."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SUPPLIERS = [
    {"supplier_id": "SUP-001", "name": "FastParts Co"},
    {"supplier_id": "SUP-005", "name": "ValueFirst Co"},
]


def po(po_id, supplier_id, expected, actual, status="delivered"):
    return {
        "po_id": po_id,
        "supplier_id": supplier_id,
        "sku_id": "SKU-003",
        "expected_delivery": expected,
        "actual_delivery": actual,
        "status": status,
    }


@pytest.fixture()
def memory(tmp_path, monkeypatch):
    from server import db
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "betsy_test.db")
    db.init_db()
    from server import memory as mem
    return mem


def ema_expected(old, performance, alpha=0.2):
    return round(min(1.0, max(0.0, alpha * performance + (1 - alpha) * old)), 4)


def test_on_time_delivery_raises_from_prior(memory):
    updates = memory.observe_deliveries(
        [po("PO-1", "SUP-001", "2026-01-10", "2026-01-10")], SUPPLIERS
    )
    assert len(updates) == 1
    expected = ema_expected(memory.NEUTRAL_PRIOR, 1.0)
    assert memory.get_score("SUP-001") == expected


def test_late_delivery_lowers_score(memory):
    updates = memory.observe_deliveries(
        [po("PO-2", "SUP-005", "2026-01-10", "2026-01-15")], SUPPLIERS
    )
    assert updates[0]["lateness_days"] == 5
    expected = ema_expected(memory.NEUTRAL_PRIOR, 0.5)
    assert memory.get_score("SUP-005") == expected


def test_idempotent_processing(memory):
    orders = [po("PO-3", "SUP-001", "2026-01-10", "2026-01-10")]
    memory.observe_deliveries(orders, SUPPLIERS)
    first = memory.get_score("SUP-001")
    updates = memory.observe_deliveries(orders, SUPPLIERS)
    assert updates == []
    assert memory.get_score("SUP-001") == first


def test_sequential_ema_chains(memory):
    memory.observe_deliveries([po("PO-4", "SUP-001", "2026-01-10", "2026-01-10")], SUPPLIERS)
    s1 = memory.get_score("SUP-001")
    memory.observe_deliveries([po("PO-5", "SUP-001", "2026-02-10", "2026-02-13")], SUPPLIERS)
    assert memory.get_score("SUP-001") == ema_expected(s1, 0.7)


def test_open_pos_ignored(memory):
    updates = memory.observe_deliveries(
        [po("PO-6", "SUP-001", "2026-01-10", None, status="in_transit")], SUPPLIERS
    )
    assert updates == []
    assert memory.get_scores() == {}


def test_unknown_supplier_gets_neutral_prior(memory):
    assert memory.get_score("SUP-999") == memory.NEUTRAL_PRIOR


def test_merge_scores_into_suppliers(memory):
    memory.observe_deliveries([po("PO-7", "SUP-001", "2026-01-10", "2026-01-10")], SUPPLIERS)
    merged = memory.merge_scores_into_suppliers([
        {"supplier_id": "SUP-001", "name": "FastParts Co"},
        {"supplier_id": "SUP-005", "name": "ValueFirst Co"},
    ])
    by_id = {m["supplier_id"]: m for m in merged}
    assert by_id["SUP-001"]["reliability_score"] > memory.NEUTRAL_PRIOR
    assert by_id["SUP-001"]["deliveries_observed"] == 1
    assert by_id["SUP-005"]["reliability_score"] == memory.NEUTRAL_PRIOR
    assert by_id["SUP-005"]["deliveries_observed"] == 0
