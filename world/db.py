"""SQLite persistence for the simulated world.

The world owns all ERP facts: inventory, suppliers (+ hidden true_reliability),
purchase orders, invoices, the sim clock and the event timeline. Serializers
emit the same JSON shapes the old in-memory mock server produced, so existing
consumers keep working — with two deliberate exceptions:
  * suppliers carry NO reliability_score (Betsy learns her own), and
  * true_reliability / arrival_day are never serialized (ground truth stays hidden).
"""
import json
import random
import sqlite3
import threading
from datetime import datetime

from world.config import (
    DEFAULT_TICK_SECONDS,
    HISTORY_GAP_DAYS,
    MOCK_DATA,
    WORLD_DB_PATH,
    WORLD_SEED,
)
from world.time_utils import day_to_iso

_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(WORLD_DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS sim_meta (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    day           INTEGER NOT NULL DEFAULT 0,
    running       INTEGER NOT NULL DEFAULT 0,
    tick_seconds  REAL    NOT NULL DEFAULT 5.0,
    seed          INTEGER NOT NULL,
    scenario_note TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS inventory (
    sku_id          TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT '',
    current_stock   INTEGER NOT NULL,
    reorder_point   INTEGER NOT NULL,
    max_stock       INTEGER NOT NULL,
    daily_usage_avg REAL NOT NULL,
    unit            TEXT NOT NULL DEFAULT '',
    unit_cost_avg   REAL NOT NULL DEFAULT 0,
    critical        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id      TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    availability     INTEGER NOT NULL DEFAULT 1,
    payment_terms    TEXT NOT NULL DEFAULT '',
    true_reliability REAL NOT NULL DEFAULT 0.9,   -- hidden ground truth, never serialized
    outage_until_day INTEGER                       -- set by supplier_outage events
);

CREATE TABLE IF NOT EXISTS supplier_catalog (
    supplier_id TEXT NOT NULL,
    sku_id      TEXT NOT NULL,
    unit_price  REAL NOT NULL,
    lead_days   INTEGER NOT NULL,
    PRIMARY KEY (supplier_id, sku_id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id        TEXT PRIMARY KEY,
    supplier_id  TEXT NOT NULL,
    sku_id       TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    unit_price   REAL NOT NULL,
    total_amount REAL NOT NULL,
    order_day    INTEGER NOT NULL,
    expected_day INTEGER NOT NULL,
    arrival_day  INTEGER,             -- hidden: when it will actually arrive
    actual_day   INTEGER,             -- set on delivery
    status       TEXT NOT NULL,       -- approved | in_transit | delivered | cancelled
    reason       TEXT NOT NULL DEFAULT '',
    requested_by TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id   TEXT PRIMARY KEY,
    supplier_id  TEXT NOT NULL,
    sku_id       TEXT NOT NULL,
    quantity     INTEGER NOT NULL,
    unit_price   REAL NOT NULL,
    total_amount REAL NOT NULL,
    invoice_day  INTEGER NOT NULL,
    po_reference TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'received'  -- received | paid | disputed
);

CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    day     INTEGER NOT NULL,
    type    TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    source  TEXT NOT NULL DEFAULT 'injected',   -- injected | script | sim
    applied INTEGER NOT NULL DEFAULT 0
);
"""


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
    seed_from_mock_data()


def _is_seeded() -> bool:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM sim_meta").fetchone()[0] > 0


def seed_from_mock_data() -> None:
    """Populate the world from mock_data/*.json. No-op if already seeded."""
    if _is_seeded():
        return

    inventory = json.loads((MOCK_DATA / "inventory.json").read_text())
    suppliers = json.loads((MOCK_DATA / "suppliers.json").read_text())
    pos       = json.loads((MOCK_DATA / "purchase_orders.json").read_text())
    invoices  = json.loads((MOCK_DATA / "invoices.json").read_text())

    # Remap seed history dates onto the sim timeline: the latest date in the
    # seed data lands HISTORY_GAP_DAYS before sim day 0, spacing preserved.
    def _parse(d: str) -> datetime:
        return datetime.fromisoformat(d[:10])

    all_dates = [_parse(p["order_date"]) for p in pos] + [_parse(i["date"]) for i in invoices]
    anchor = max(all_dates)

    def to_day(d: str | None) -> int | None:
        if not d:
            return None
        return (_parse(d) - anchor).days - HISTORY_GAP_DAYS

    rng = random.Random(f"{WORLD_SEED}:seed")

    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO sim_meta (id, day, running, tick_seconds, seed) VALUES (1, 0, 0, ?, ?)",
            (DEFAULT_TICK_SECONDS, WORLD_SEED),
        )
        for item in inventory:
            c.execute(
                "INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item["sku_id"], item["name"], item.get("category", ""),
                    item["current_stock"], item["reorder_point"], item["max_stock"],
                    item["daily_usage_avg"], item.get("unit", ""),
                    item.get("unit_cost_avg", 0), int(item.get("critical", False)),
                ),
            )
        for sup in suppliers:
            # The POC's reliability_score becomes the world's hidden ground truth.
            c.execute(
                "INSERT INTO suppliers (supplier_id, name, availability, payment_terms, true_reliability) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    sup["supplier_id"], sup["name"], int(sup.get("availability", True)),
                    sup.get("payment_terms", ""), sup.get("reliability_score", 0.9),
                ),
            )
            for sku_id, entry in sup.get("catalog", {}).items():
                c.execute(
                    "INSERT INTO supplier_catalog VALUES (?, ?, ?, ?)",
                    (sup["supplier_id"], sku_id, entry["unit_price"], entry["lead_days"]),
                )
        for po in pos:
            order_day    = to_day(po["order_date"])
            expected_day = to_day(po["expected_delivery"])
            actual_day   = to_day(po.get("actual_delivery"))
            if po["status"] == "delivered":
                arrival_day = actual_day
            else:
                # Open seeded PO: draw its hidden arrival now; never before day 1.
                sup = next(s for s in suppliers if s["supplier_id"] == po["supplier_id"])
                arrival_day = max(1, draw_arrival_day(rng, expected_day, sup.get("reliability_score", 0.9)))
            c.execute(
                "INSERT INTO purchase_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    po["po_id"], po["supplier_id"], po["sku_id"], po["quantity"],
                    po["unit_price"], po["total_amount"], order_day, expected_day,
                    arrival_day, actual_day, po["status"], po.get("reason", ""),
                    po.get("requested_by", ""),
                ),
            )
        for inv in invoices:
            c.execute(
                "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    inv["invoice_id"], inv["supplier_id"], inv["sku_id"], inv["quantity"],
                    inv["unit_price"], inv["total_amount"], to_day(inv["date"]),
                    inv.get("po_reference", ""), inv.get("status", "received"),
                ),
            )


def reset_to_seed() -> None:
    with _lock, _conn() as c:
        for table in ("sim_meta", "inventory", "suppliers", "supplier_catalog",
                      "purchase_orders", "invoices", "events"):
            c.execute(f"DELETE FROM {table}")
    seed_from_mock_data()


# ── Hidden delivery jitter (sole consumer of true_reliability) ────────────────

def draw_arrival_day(rng: random.Random, expected_day: int, true_reliability: float) -> int:
    """On time with probability true_reliability, else late by 1+Exp(1.5) days."""
    if rng.random() < true_reliability:
        return expected_day
    return expected_day + 1 + int(rng.expovariate(1.5))


# ── Clock ─────────────────────────────────────────────────────────────────────

def get_meta() -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM sim_meta WHERE id = 1").fetchone()
    return dict(r)


def set_meta(**fields) -> None:
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE sim_meta SET {cols} WHERE id = 1", tuple(fields.values()))


def current_day() -> int:
    return get_meta()["day"]


# ── Serializers (legacy JSON shapes) ──────────────────────────────────────────

def serialize_inventory(r: sqlite3.Row) -> dict:
    return {
        "sku_id": r["sku_id"], "name": r["name"], "category": r["category"],
        "current_stock": r["current_stock"], "reorder_point": r["reorder_point"],
        "max_stock": r["max_stock"], "daily_usage_avg": r["daily_usage_avg"],
        "unit": r["unit"], "unit_cost_avg": r["unit_cost_avg"],
        "critical": bool(r["critical"]),
    }


def serialize_po(r: sqlite3.Row) -> dict:
    return {
        "po_id": r["po_id"], "supplier_id": r["supplier_id"], "sku_id": r["sku_id"],
        "quantity": r["quantity"], "unit_price": r["unit_price"],
        "total_amount": r["total_amount"],
        "order_date": day_to_iso(r["order_day"]),
        "expected_delivery": day_to_iso(r["expected_day"]),
        "actual_delivery": day_to_iso(r["actual_day"]),
        "status": r["status"], "reason": r["reason"], "requested_by": r["requested_by"],
    }


def serialize_invoice(r: sqlite3.Row) -> dict:
    return {
        "invoice_id": r["invoice_id"], "supplier_id": r["supplier_id"],
        "sku_id": r["sku_id"], "quantity": r["quantity"], "unit_price": r["unit_price"],
        "total_amount": r["total_amount"], "date": day_to_iso(r["invoice_day"]),
        "po_reference": r["po_reference"], "status": r["status"],
    }


def serialize_event(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "day": r["day"], "date": day_to_iso(r["day"]),
        "type": r["type"], "payload": json.loads(r["payload"]),
        "source": r["source"], "applied": bool(r["applied"]),
    }


# ── Reads ─────────────────────────────────────────────────────────────────────

def get_inventory() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM inventory ORDER BY sku_id").fetchall()
    return [serialize_inventory(r) for r in rows]


def get_suppliers() -> list[dict]:
    """Public supplier payloads — no true_reliability, no score."""
    with _conn() as c:
        sups = c.execute("SELECT * FROM suppliers ORDER BY supplier_id").fetchall()
        cats = c.execute("SELECT * FROM supplier_catalog").fetchall()
    catalog: dict[str, dict] = {}
    for r in cats:
        catalog.setdefault(r["supplier_id"], {})[r["sku_id"]] = {
            "unit_price": r["unit_price"], "lead_days": r["lead_days"],
        }
    return [
        {
            "supplier_id": s["supplier_id"], "name": s["name"],
            "availability": bool(s["availability"]),
            "payment_terms": s["payment_terms"],
            "catalog": catalog.get(s["supplier_id"], {}),
        }
        for s in sups
    ]


def get_purchase_orders() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM purchase_orders ORDER BY order_day, po_id").fetchall()
    return [serialize_po(r) for r in rows]


def get_invoices() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM invoices ORDER BY invoice_day, invoice_id").fetchall()
    return [serialize_invoice(r) for r in rows]
