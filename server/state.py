import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).parent.parent
MOCK_DATA = ROOT / "mock_data"
SCENARIOS = ROOT / "scenarios"

VALID_SCENARIOS = ["stockout_warning", "price_spike", "duplicate_invoice", "supplier_oos"]


class AppState:
    def __init__(self):
        self._base: dict = {}
        self._current: dict = {}
        self.agent_log: list = []
        self.approvals: list = []
        self.active_scenario: str = "normal"
        self.load()
        from server import db as _db
        _db.init_db()
        self.agent_log = _db.load_log_entries()
        self.approvals = _db.load_all_approvals()

    def load(self):
        self._base = {
            "inventory": json.loads((MOCK_DATA / "inventory.json").read_text()),
            "suppliers": json.loads((MOCK_DATA / "suppliers.json").read_text()),
            "purchase_orders": json.loads((MOCK_DATA / "purchase_orders.json").read_text()),
            "invoices": json.loads((MOCK_DATA / "invoices.json").read_text()),
        }
        self._current = deepcopy(self._base)
        self.agent_log = []
        self.active_scenario = "normal"

    def reset(self):
        self._current = deepcopy(self._base)
        self.agent_log = []
        self.active_scenario = "normal"
        from server import db as _db
        _db.clear_log()

    def apply_scenario(self, name: str) -> dict:
        path = SCENARIOS / f"{name}.json"
        scenario = json.loads(path.read_text())
        self._current = deepcopy(self._base)
        self.agent_log = []
        self.active_scenario = name

        for key, overrides in scenario.get("overrides", {}).items():
            if key == "inventory":
                for override_item in overrides:
                    for item in self._current["inventory"]:
                        if item["sku_id"] == override_item["sku_id"]:
                            item.update(override_item)
                            break
            elif key == "suppliers":
                for override_item in overrides:
                    for supplier in self._current["suppliers"]:
                        if supplier["supplier_id"] == override_item["supplier_id"]:
                            for k, v in override_item.items():
                                if k == "catalog" and isinstance(v, dict):
                                    for sku_id, sku_data in v.items():
                                        if sku_id in supplier["catalog"]:
                                            supplier["catalog"][sku_id].update(sku_data)
                                        else:
                                            supplier["catalog"][sku_id] = sku_data
                                else:
                                    supplier[k] = v
                            break
            elif key == "invoices":
                self._current["invoices"].extend(overrides)

        return scenario

    @property
    def inventory(self) -> list:
        return self._current["inventory"]

    @property
    def suppliers(self) -> list:
        return self._current["suppliers"]

    @property
    def purchase_orders(self) -> list:
        return self._current["purchase_orders"]

    @property
    def invoices(self) -> list:
        return self._current["invoices"]


state = AppState()
