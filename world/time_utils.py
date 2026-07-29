from datetime import date, datetime, timedelta

from world.config import SIM_EPOCH


def day_to_iso(day: int | None) -> str | None:
    """Sim day number -> ISO date string (YYYY-MM-DD)."""
    if day is None:
        return None
    return (SIM_EPOCH + timedelta(days=day)).isoformat()


def iso_to_day(value: str) -> int:
    """ISO date or datetime string -> sim day number."""
    d = datetime.fromisoformat(value[:10]).date()
    return (d - SIM_EPOCH).days


def day_to_date(day: int) -> date:
    return SIM_EPOCH + timedelta(days=day)
