"""Stage 1 -- fetch all data from the mock API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from pipeline.state import PipelineState


def run(offline: bool = False) -> dict:
    """Pure ingest -- returns dict to merge into state. Callable standalone."""
    if offline:
        inventory = api.load_inventory()
        suppliers = api.load_suppliers()
        all_pos = api.load_purchase_orders()
        invoices = api.load_invoices()
    else:
        inventory = api.get_inventory()
        suppliers = api.get_suppliers()
        all_pos = api.get_purchase_orders()
        invoices = api.get_invoices()

    open_statuses = {"delivered", "cancelled"}
    open_pos = [po for po in all_pos if po.get("status") not in open_statuses]

    return {
        "inventory": inventory,
        "suppliers": suppliers,
        "all_pos": all_pos,
        "open_pos": open_pos,
        "invoices": invoices,
        "detected": [],
        "evaluated": [],
        "decisions": [],
        "actions": [],
        "report": "",
        "errors": [],
    }


def node(state: PipelineState) -> dict:
    """LangGraph node -- wraps run()."""
    try:
        return run(offline=False)
    except Exception as exc:
        return {"errors": [f"ingest: {exc}"]}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    print("\n" + "=" * 60)
    print("PIPELINE -- Stage: ingest")
    print("=" * 60)

    offline = not api.is_server_up()
    mode = "offline (JSON files)" if offline else f"live API ({api.API_BASE})"
    print(f"Mode: {mode}")

    result = run(offline=offline)
    print(f"\nLoaded:")
    print(f"  Inventory:        {len(result['inventory'])} SKUs")
    print(f"  Suppliers:        {len(result['suppliers'])} suppliers")
    print(f"  Purchase orders:  {len(result['all_pos'])} total, {len(result['open_pos'])} open")
    print(f"  Invoices:         {len(result['invoices'])} invoices")

    print(f"\nSample SKU:  {result['inventory'][0]['sku_id']} -- {result['inventory'][0]['name']}")
    print(f"Sample SUP:  {result['suppliers'][0]['supplier_id']} -- {result['suppliers'][0]['name']}")
    print("=" * 60)
