"""HTTP client used by the agents (orchestra / pipeline).

World data (inventory, POs, invoices) comes straight from the world service.
Suppliers come from Betsy's API, which merges in her learned reliability
scores — the agents never see the world's hidden ground truth.
Approvals and decision logs are Betsy application state on port 8000.
"""
import json
import os
from pathlib import Path

import httpx

from shared import world_client

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
MOCK_DIR = Path(__file__).parent.parent / "mock_data"


# ── Offline loaders (from JSON files -- no server needed) ─────────────────────

def load_inventory() -> list:
    return json.loads((MOCK_DIR / "inventory.json").read_text())


def load_suppliers() -> list:
    return json.loads((MOCK_DIR / "suppliers.json").read_text())


def load_purchase_orders() -> list:
    return json.loads((MOCK_DIR / "purchase_orders.json").read_text())


def load_invoices() -> list:
    return json.loads((MOCK_DIR / "invoices.json").read_text())


# ── World data ────────────────────────────────────────────────────────────────

def get_inventory() -> list:
    return world_client.get_inventory()


def get_purchase_orders() -> list:
    return world_client.get_purchase_orders()


def get_invoices() -> list:
    return world_client.get_invoices()


def get_snapshot() -> dict:
    return world_client.get_snapshot()


def get_suppliers() -> list:
    """Suppliers with Betsy's learned reliability_score merged in."""
    return httpx.get(f"{API_BASE}/api/suppliers", timeout=5.0).json()


def _post_purchase_order(payload: dict) -> dict:
    return world_client.create_po(payload)


# ── Betsy application state ───────────────────────────────────────────────────

def log_decision(trigger: str, analysis: str, decision: str,
                 confidence: float, metadata: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}/api/agent-log", json={
            "trigger": trigger,
            "analysis": analysis,
            "decision": decision,
            "confidence": confidence,
            "metadata": metadata,
        }, timeout=5.0)
        return r.json()
    except Exception:
        return {"logged": False}


def queue_approval(item: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}/api/approvals", json=item, timeout=5.0)
        return r.json()
    except Exception:
        return {"queued": False}


def is_server_up() -> bool:
    try:
        httpx.get(f"{API_BASE}/health", timeout=2.0)
        return True
    except Exception:
        return False
