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
        """)


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


def load_all_approvals() -> list:
    with _conn() as c:
        rows = c.execute("SELECT * FROM approvals ORDER BY id ASC").fetchall()
    return [
        {
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
        for r in rows
    ]
