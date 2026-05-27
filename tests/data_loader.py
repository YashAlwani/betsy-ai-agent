"""Load and validate mock data files."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DATA = ROOT / "mock_data"
SCENARIOS = ROOT / "scenarios"


def load_inventory() -> list:
    return json.loads((MOCK_DATA / "inventory.json").read_text())


def load_suppliers() -> list:
    return json.loads((MOCK_DATA / "suppliers.json").read_text())


def load_purchase_orders() -> list:
    return json.loads((MOCK_DATA / "purchase_orders.json").read_text())


def load_invoices() -> list:
    return json.loads((MOCK_DATA / "invoices.json").read_text())


def load_scenario(name: str) -> dict:
    return json.loads((SCENARIOS / f"{name}.json").read_text())


def validate_data() -> list[str]:
    inventory = load_inventory()
    suppliers = load_suppliers()
    purchase_orders = load_purchase_orders()
    invoices = load_invoices()

    sku_ids = {item["sku_id"] for item in inventory}
    supplier_ids = {sup["supplier_id"] for sup in suppliers}
    errors = []

    for po in purchase_orders:
        if po["supplier_id"] not in supplier_ids:
            errors.append(f"PO {po['po_id']} references unknown supplier {po['supplier_id']}")
        if po["sku_id"] not in sku_ids:
            errors.append(f"PO {po['po_id']} references unknown SKU {po['sku_id']}")

    for inv in invoices:
        if inv["supplier_id"] not in supplier_ids:
            errors.append(f"Invoice {inv['invoice_id']} references unknown supplier {inv['supplier_id']}")
        if inv["sku_id"] not in sku_ids:
            errors.append(f"Invoice {inv['invoice_id']} references unknown SKU {inv['sku_id']}")

    for sup in suppliers:
        for sku_id in sup.get("catalog", {}):
            if sku_id not in sku_ids:
                errors.append(f"Supplier {sup['supplier_id']} catalog references unknown SKU {sku_id}")

    return errors


if __name__ == "__main__":
    print("Loading mock data...")
    inventory = load_inventory()
    suppliers = load_suppliers()
    purchase_orders = load_purchase_orders()
    invoices = load_invoices()

    print(f"  Inventory     : {len(inventory)} SKUs")
    print(f"  Suppliers     : {len(suppliers)}")
    print(f"  Purchase Orders: {len(purchase_orders)}")
    print(f"  Invoices      : {len(invoices)}")

    below_reorder = [i for i in inventory if i["current_stock"] < i["reorder_point"]]
    print(f"\nItems below reorder point ({len(below_reorder)}):")
    for item in below_reorder:
        days = item["current_stock"] / item["daily_usage_avg"]
        print(f"  {item['sku_id']} {item['name']}: stock={item['current_stock']} "
              f"reorder={item['reorder_point']} days_left={days:.1f}")

    errors = validate_data()
    if errors:
        print(f"\nValidation ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print("\nValidation: all referential integrity checks passed")
