import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "betsy.db"
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _lock, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS agent_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT NOT NULL,
                trigger    TEXT NOT NULL,
                analysis   TEXT NOT NULL,
                decision   TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                metadata   TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT UNIQUE NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                action      TEXT NOT NULL,
                sku_id      TEXT,
                supplier_id TEXT,
                po_total    REAL,
                qty         INTEGER,
                unit_price  REAL,
                confidence  REAL NOT NULL DEFAULT 0.5,
                reasoning   TEXT,
                payload     TEXT,
                created_at  TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS supplier_scores (
                supplier_id          TEXT PRIMARY KEY,
                reliability_score    REAL NOT NULL,
                deliveries_observed  INTEGER NOT NULL DEFAULT 0,
                updated_at           TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS processed_deliveries (
                po_id         TEXT PRIMARY KEY,
                processed_at  TEXT NOT NULL,
                lateness_days INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS agent_cursor (
                id           INTEGER PRIMARY KEY CHECK (id = 1),
                last_run_day INTEGER NOT NULL DEFAULT -1,
                last_run_at  TEXT
            );
        """)
        c.execute("INSERT OR IGNORE INTO agent_cursor (id, last_run_day) VALUES (1, -1)")


# ── agent_log ─────────────────────────────────────────────────────────────────

def save_log_entry(entry: dict) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO agent_log (timestamp, trigger, analysis, decision, confidence, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.get("timestamp", datetime.now().isoformat()),
                entry.get("trigger", ""),
                entry.get("analysis", ""),
                entry.get("decision", ""),
                entry.get("confidence", 0.0),
                json.dumps(entry.get("metadata", {})),
            ),
        )


def load_log_entries() -> list:
    with _conn() as c:
        rows = c.execute("SELECT * FROM agent_log ORDER BY id ASC").fetchall()
    return [
        {
            "timestamp": r["timestamp"],
            "trigger":   r["trigger"],
            "analysis":  r["analysis"],
            "decision":  r["decision"],
            "confidence": r["confidence"],
            "metadata":  json.loads(r["metadata"]),
        }
        for r in rows
    ]


def clear_log() -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM agent_log")


# ── approvals ─────────────────────────────────────────────────────────────────

def save_approval(item: dict) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO approvals "
            "(decision_id, status, action, sku_id, supplier_id, po_total, qty, "
            " unit_price, confidence, reasoning, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item["decision_id"],
                item.get("status", "pending"),
                item.get("action", ""),
                item.get("sku_id", ""),
                item.get("supplier_id", ""),
                item.get("po_total", 0),
                item.get("qty", 0),
                item.get("unit_price", 0),
                item.get("confidence", 0.5),
                item.get("reasoning", ""),
                json.dumps(item.get("payload")) if item.get("payload") else None,
                item.get("created_at", datetime.now().isoformat()),
            ),
        )


def update_approval(decision_id: str, status: str, resolved_at: str) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE approvals SET status = ?, resolved_at = ? WHERE decision_id = ?",
            (status, resolved_at, decision_id),
        )


def _approval_row_to_dict(r) -> dict:
    return {
        "decision_id": r["decision_id"],
        "status":      r["status"],
        "action":      r["action"],
        "sku_id":      r["sku_id"],
        "supplier_id": r["supplier_id"],
        "po_total":    r["po_total"],
        "qty":         r["qty"],
        "unit_price":  r["unit_price"],
        "confidence":  r["confidence"],
        "reasoning":   r["reasoning"],
        "payload":     json.loads(r["payload"]) if r["payload"] else None,
        "created_at":  r["created_at"],
        "resolved_at": r["resolved_at"],
    }


def load_pending_approvals() -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM approvals WHERE status = 'pending' ORDER BY id ASC"
        ).fetchall()
    return [_approval_row_to_dict(r) for r in rows]


def get_approval(decision_id: str) -> dict | None:
    with _conn() as c:
        r = c.execute(
            "SELECT * FROM approvals WHERE decision_id = ?", (decision_id,)
        ).fetchone()
    return _approval_row_to_dict(r) if r else None


def load_all_approvals() -> list:
    with _conn() as c:
        rows = c.execute("SELECT * FROM approvals ORDER BY id ASC").fetchall()
    return [_approval_row_to_dict(r) for r in rows]


# ── supplier memory (Betsy's learned scores) ──────────────────────────────────

def load_supplier_scores() -> dict:
    """supplier_id -> {reliability_score, deliveries_observed, updated_at}"""
    with _conn() as c:
        rows = c.execute("SELECT * FROM supplier_scores").fetchall()
    return {
        r["supplier_id"]: {
            "reliability_score":   r["reliability_score"],
            "deliveries_observed": r["deliveries_observed"],
            "updated_at":          r["updated_at"],
        }
        for r in rows
    }


def upsert_supplier_score(supplier_id: str, score: float, deliveries_observed: int) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO supplier_scores (supplier_id, reliability_score, deliveries_observed, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(supplier_id) DO UPDATE SET "
            "reliability_score = excluded.reliability_score, "
            "deliveries_observed = excluded.deliveries_observed, "
            "updated_at = excluded.updated_at",
            (supplier_id, score, deliveries_observed, datetime.now().isoformat()),
        )


def load_processed_deliveries() -> set:
    with _conn() as c:
        rows = c.execute("SELECT po_id FROM processed_deliveries").fetchall()
    return {r["po_id"] for r in rows}


def mark_delivery_processed(po_id: str, lateness_days: int) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO processed_deliveries (po_id, processed_at, lateness_days) "
            "VALUES (?, ?, ?)",
            (po_id, datetime.now().isoformat(), lateness_days),
        )


def get_agent_cursor() -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM agent_cursor WHERE id = 1").fetchone()
    return {"last_run_day": r["last_run_day"], "last_run_at": r["last_run_at"]} if r else \
           {"last_run_day": -1, "last_run_at": None}


def set_agent_cursor(day: int) -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE agent_cursor SET last_run_day = ?, last_run_at = ? WHERE id = 1",
            (day, datetime.now().isoformat()),
        )
