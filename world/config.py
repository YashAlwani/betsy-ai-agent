import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent

WORLD_DB_PATH = Path(os.getenv("WORLD_DB_PATH", str(ROOT / "world.db")))
MOCK_DATA = ROOT / "mock_data"
SCENARIOS = Path(__file__).parent / "scenarios"

# sim_day 0 maps to this calendar date; all API payloads emit ISO dates from it
SIM_EPOCH = date(2026, 1, 1)

# Seeded history is remapped so its latest date lands this many days before day 0
HISTORY_GAP_DAYS = 14

WORLD_SEED = int(os.getenv("WORLD_SEED", "42"))
DEFAULT_TICK_SECONDS = float(os.getenv("TICK_SECONDS", "5.0"))
