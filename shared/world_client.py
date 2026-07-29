"""Adapter between Betsy and the world (simulated ERP).

Everything Betsy knows about the outside world flows through this client.
Pointing Betsy at a real ERP means re-implementing this module only.
"""
import os

import httpx

WORLD_BASE = os.getenv("WORLD_BASE_URL", "http://localhost:8001")
TIMEOUT = 10.0


# ── Data reads ────────────────────────────────────────────────────────────────

def get_inventory() -> list:
    return httpx.get(f"{WORLD_BASE}/api/inventory", timeout=TIMEOUT).json()


def get_suppliers() -> list:
    """Raw world suppliers — objective facts only, no reliability score."""
    return httpx.get(f"{WORLD_BASE}/api/suppliers", timeout=TIMEOUT).json()


def get_purchase_orders() -> list:
    return httpx.get(f"{WORLD_BASE}/api/purchase-orders", timeout=TIMEOUT).json()


def get_invoices() -> list:
    return httpx.get(f"{WORLD_BASE}/api/invoices", timeout=TIMEOUT).json()


def get_snapshot() -> dict:
    """All world data in one consistent read (clock, inventory, suppliers, POs, invoices)."""
    return httpx.get(f"{WORLD_BASE}/api/snapshot", timeout=TIMEOUT).json()


def get_quote(supplier_id: str, sku_id: str, quantity: int = 1) -> dict:
    r = httpx.get(
        f"{WORLD_BASE}/api/suppliers/{supplier_id}/quote",
        params={"sku_id": sku_id, "quantity": quantity},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Writes ────────────────────────────────────────────────────────────────────

def create_po(payload: dict) -> dict:
    r = httpx.post(f"{WORLD_BASE}/api/purchase-orders", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def patch_invoice_status(invoice_id: str, status: str) -> dict:
    r = httpx.patch(
        f"{WORLD_BASE}/api/invoices/{invoice_id}/status",
        params={"status": status},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


# ── Sim clock / events ────────────────────────────────────────────────────────

def get_clock() -> dict:
    return httpx.get(f"{WORLD_BASE}/api/clock", timeout=TIMEOUT).json()


def play() -> dict:
    return httpx.post(f"{WORLD_BASE}/api/clock/play", timeout=TIMEOUT).json()


def pause() -> dict:
    return httpx.post(f"{WORLD_BASE}/api/clock/pause", timeout=TIMEOUT).json()


def step(days: int = 1) -> dict:
    r = httpx.post(f"{WORLD_BASE}/api/clock/step", params={"days": days}, timeout=60.0)
    r.raise_for_status()
    return r.json()


def set_speed(tick_seconds: float) -> dict:
    return httpx.post(
        f"{WORLD_BASE}/api/clock/speed", params={"tick_seconds": tick_seconds}, timeout=TIMEOUT
    ).json()


def get_events(since: int = 0, limit: int = 100) -> list:
    return httpx.get(
        f"{WORLD_BASE}/api/events", params={"since": since, "limit": limit}, timeout=TIMEOUT
    ).json()


def list_scripts() -> list:
    return httpx.get(f"{WORLD_BASE}/api/events/scripts", timeout=TIMEOUT).json()


def inject_event(event: dict) -> dict:
    r = httpx.post(f"{WORLD_BASE}/api/events", json=event, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def inject_script(name: str) -> dict:
    r = httpx.post(f"{WORLD_BASE}/api/events/script/{name}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def reset_world() -> dict:
    return httpx.post(f"{WORLD_BASE}/api/admin/reset", timeout=30.0).json()


def is_up() -> bool:
    try:
        httpx.get(f"{WORLD_BASE}/health", timeout=2.0)
        return True
    except Exception:
        return False
