"""The tick engine: one call to tick() advances the world by one simulated day.

Everything happens in a single SQLite transaction under the module lock, so an
API reader never observes a half-applied day. Randomness is deterministic per
(seed, day): replaying the same seed and steps reproduces the identical world.
"""
import json
import random
import uuid

from world import db
from world.time_utils import day_to_date

# Ambient event probabilities (per tick)
P_PRICE_DRIFT = 0.10   # one random catalog entry drifts ±2%
P_OUTAGE      = 0.02   # a random supplier goes down for 1-3 days
# Invoice generation faults (per delivered PO)
P_DUP_INVOICE = 0.05
P_AMOUNT_ERR  = 0.05


def tick() -> dict:
    """Advance the sim by one day. Returns a summary of what happened."""
    summary = {
        "day": None, "date": None, "consumed": {}, "delivered": [],
        "invoices": [], "events_applied": [], "ambient": [],
    }

    with db._lock, db._conn() as c:
        meta = c.execute("SELECT * FROM sim_meta WHERE id = 1").fetchone()
        day = meta["day"] + 1
        seed = meta["seed"]
        rng = random.Random(f"{seed}:{day}")
        c.execute("UPDATE sim_meta SET day = ? WHERE id = 1", (day,))
        summary["day"] = day
        summary["date"] = day_to_date(day).isoformat()

        _end_expired_outages(c, day)
        summary["events_applied"] = _apply_due_events(c, day, rng)
        summary["consumed"] = _consume_stock(c, rng)
        delivered, invoices = _progress_pos(c, day, rng)
        summary["delivered"] = delivered
        summary["invoices"] = invoices
        summary["ambient"] = _ambient_events(c, day, rng)

        c.execute(
            "INSERT INTO events (day, type, payload, source, applied) VALUES (?, ?, ?, 'sim', 1)",
            (day, "tick_summary", json.dumps({
                "consumed_total": sum(summary["consumed"].values()),
                "delivered": [d["po_id"] for d in delivered],
                "invoices": [i["invoice_id"] for i in invoices],
                "events_applied": summary["events_applied"],
                "ambient": summary["ambient"],
            })),
        )

    return summary


# ── Injected / scripted events ────────────────────────────────────────────────

def _apply_due_events(c, day: int, rng: random.Random) -> list:
    applied = []
    rows = c.execute(
        "SELECT * FROM events WHERE applied = 0 AND day <= ? AND source != 'sim' ORDER BY id",
        (day,),
    ).fetchall()
    for row in rows:
        payload = json.loads(row["payload"])
        handler = _EVENT_HANDLERS.get(row["type"])
        if handler:
            handler(c, day, payload, rng)
            applied.append(f"{row['type']}#{row['id']}")
        c.execute("UPDATE events SET applied = 1 WHERE id = ?", (row["id"],))
    return applied


def _ev_price_change(c, day, p, rng):
    c.execute(
        "UPDATE supplier_catalog SET unit_price = ? WHERE supplier_id = ? AND sku_id = ?",
        (p["unit_price"], p["supplier_id"], p["sku_id"]),
    )


def _ev_stock_set(c, day, p, rng):
    c.execute(
        "UPDATE inventory SET current_stock = ? WHERE sku_id = ?",
        (p["current_stock"], p["sku_id"]),
    )


def _ev_usage_spike(c, day, p, rng):
    """Multiply a SKU's daily usage (factor, e.g. 2.0). Permanent until changed again."""
    c.execute(
        "UPDATE inventory SET daily_usage_avg = round(daily_usage_avg * ?, 2) WHERE sku_id = ?",
        (p.get("factor", 2.0), p["sku_id"]),
    )


def _ev_supplier_outage(c, day, p, rng):
    duration = p.get("duration_days")
    until = day + duration if duration else None
    c.execute(
        "UPDATE suppliers SET availability = 0, outage_until_day = ? WHERE supplier_id = ?",
        (until, p["supplier_id"]),
    )


def _ev_duplicate_invoice(c, day, p, rng):
    """Re-issue an existing invoice (by id, or the latest for a supplier)."""
    if p.get("invoice_id"):
        src = c.execute("SELECT * FROM invoices WHERE invoice_id = ?", (p["invoice_id"],)).fetchone()
    else:
        src = c.execute(
            "SELECT * FROM invoices WHERE supplier_id = ? ORDER BY invoice_day DESC LIMIT 1",
            (p.get("supplier_id", ""),),
        ).fetchone()
    if src:
        _insert_invoice(c, day, src["supplier_id"], src["sku_id"], src["quantity"],
                        src["unit_price"], src["total_amount"], src["po_reference"])


def _ev_invoice_error(c, day, p, rng):
    """Issue an invoice with an inflated amount against an existing PO."""
    po = c.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (p.get("po_reference", ""),)).fetchone()
    if po:
        factor = p.get("factor", 1.15)
        _insert_invoice(c, day, po["supplier_id"], po["sku_id"], po["quantity"],
                        round(po["unit_price"] * factor, 2),
                        round(po["total_amount"] * factor, 2), po["po_id"])


_EVENT_HANDLERS = {
    "price_change":      _ev_price_change,
    "stock_set":         _ev_stock_set,
    "usage_spike":       _ev_usage_spike,
    "supplier_outage":   _ev_supplier_outage,
    "duplicate_invoice": _ev_duplicate_invoice,
    "invoice_error":     _ev_invoice_error,
}


def _end_expired_outages(c, day: int) -> None:
    c.execute(
        "UPDATE suppliers SET availability = 1, outage_until_day = NULL "
        "WHERE outage_until_day IS NOT NULL AND outage_until_day <= ?",
        (day,),
    )


# ── Daily world physics ───────────────────────────────────────────────────────

def _consume_stock(c, rng: random.Random) -> dict:
    consumed = {}
    for row in c.execute("SELECT sku_id, current_stock, daily_usage_avg FROM inventory").fetchall():
        usage = max(0, round(rng.gauss(row["daily_usage_avg"], 0.25 * row["daily_usage_avg"])))
        new_stock = max(0, row["current_stock"] - usage)
        if usage:
            c.execute("UPDATE inventory SET current_stock = ? WHERE sku_id = ?",
                      (new_stock, row["sku_id"]))
            consumed[row["sku_id"]] = row["current_stock"] - new_stock
    return consumed


def _progress_pos(c, day: int, rng: random.Random) -> tuple[list, list]:
    delivered, invoices = [], []

    # approved POs ship the day after ordering
    c.execute(
        "UPDATE purchase_orders SET status = 'in_transit' "
        "WHERE status = 'approved' AND order_day < ?",
        (day,),
    )

    rows = c.execute(
        "SELECT * FROM purchase_orders WHERE status IN ('approved', 'in_transit') "
        "AND arrival_day IS NOT NULL AND arrival_day <= ?",
        (day,),
    ).fetchall()
    for po in rows:
        c.execute(
            "UPDATE purchase_orders SET status = 'delivered', actual_day = ? WHERE po_id = ?",
            (day, po["po_id"]),
        )
        c.execute(
            "UPDATE inventory SET current_stock = MIN(max_stock, current_stock + ?) WHERE sku_id = ?",
            (po["quantity"], po["sku_id"]),
        )
        delivered.append({"po_id": po["po_id"], "supplier_id": po["supplier_id"],
                          "sku_id": po["sku_id"], "quantity": po["quantity"]})

        # supplier issues the invoice on delivery; occasionally makes mistakes
        amount = po["total_amount"]
        unit_price = po["unit_price"]
        if rng.random() < P_AMOUNT_ERR:
            factor = 1 + rng.uniform(0.05, 0.25)
            amount = round(amount * factor, 2)
            unit_price = round(unit_price * factor, 2)
        inv_id = _insert_invoice(c, day, po["supplier_id"], po["sku_id"], po["quantity"],
                                 unit_price, amount, po["po_id"])
        invoices.append({"invoice_id": inv_id, "po_reference": po["po_id"], "amount": amount})

        if rng.random() < P_DUP_INVOICE:
            dup_id = _insert_invoice(c, day, po["supplier_id"], po["sku_id"], po["quantity"],
                                     unit_price, amount, po["po_id"])
            invoices.append({"invoice_id": dup_id, "po_reference": po["po_id"],
                             "amount": amount, "duplicate": True})

    return delivered, invoices


def _ambient_events(c, day: int, rng: random.Random) -> list:
    ambient = []
    if rng.random() < P_PRICE_DRIFT:
        row = c.execute(
            "SELECT supplier_id, sku_id, unit_price FROM supplier_catalog "
            "ORDER BY supplier_id, sku_id LIMIT 1 OFFSET ?",
            (rng.randrange(_catalog_count(c)),),
        ).fetchone()
        if row:
            drift = 1 + rng.uniform(-0.02, 0.02)
            new_price = round(row["unit_price"] * drift, 4)
            c.execute(
                "UPDATE supplier_catalog SET unit_price = ? WHERE supplier_id = ? AND sku_id = ?",
                (new_price, row["supplier_id"], row["sku_id"]),
            )
            ambient.append(f"price_drift {row['supplier_id']}/{row['sku_id']} -> {new_price}")

    if rng.random() < P_OUTAGE:
        sup = c.execute(
            "SELECT supplier_id FROM suppliers WHERE availability = 1 "
            "ORDER BY supplier_id LIMIT 1 OFFSET ?",
            (rng.randrange(max(1, _supplier_count(c))),),
        ).fetchone()
        if sup:
            duration = rng.randint(1, 3)
            c.execute(
                "UPDATE suppliers SET availability = 0, outage_until_day = ? WHERE supplier_id = ?",
                (day + duration, sup["supplier_id"]),
            )
            ambient.append(f"outage {sup['supplier_id']} for {duration}d")
    return ambient


def _catalog_count(c) -> int:
    return c.execute("SELECT COUNT(*) FROM supplier_catalog").fetchone()[0]


def _supplier_count(c) -> int:
    return c.execute("SELECT COUNT(*) FROM suppliers WHERE availability = 1").fetchone()[0]


def _insert_invoice(c, day: int, supplier_id: str, sku_id: str, quantity: int,
                    unit_price: float, total_amount: float, po_reference: str) -> str:
    stamp = day_to_date(day).strftime("%Y%m%d")
    inv_id = f"INV-{stamp}-{str(uuid.uuid4())[:4].upper()}"
    c.execute(
        "INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'received')",
        (inv_id, supplier_id, sku_id, quantity, unit_price, total_amount, day, po_reference),
    )
    return inv_id
