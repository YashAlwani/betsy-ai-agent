"""Notification configuration.

Variables are module-level so they can be mutated at runtime via
POST /api/notifications/config without restarting the server.
On restart, values fall back to environment variables (or .env file).
"""
import os

from dotenv import load_dotenv

load_dotenv(override=False)  # .env values only fill gaps not already in the environment

# ── Desktop notifications (plyer) ─────────────────────────────────────────────
NOTIFY_DESKTOP = os.getenv("NOTIFY_DESKTOP", "true").lower() == "true"

# ── Email notifications (SMTP) ────────────────────────────────────────────────
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")
SMTP_HOST    = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")

# ── Per-trigger toggles ───────────────────────────────────────────────────────
NOTIFY_ON_APPROVAL   = os.getenv("NOTIFY_ON_APPROVAL",   "true").lower()  == "true"
NOTIFY_ON_AUTO_PO    = os.getenv("NOTIFY_ON_AUTO_PO",    "false").lower() == "true"
NOTIFY_ON_SCORE_DROP = os.getenv("NOTIFY_ON_SCORE_DROP", "true").lower()  == "true"
NOTIFY_ON_DUPLICATE  = os.getenv("NOTIFY_ON_DUPLICATE",  "true").lower()  == "true"

# Score must cross below this threshold (not just be below it) to trigger an alert
SCORE_DROP_THRESHOLD = float(os.getenv("SCORE_DROP_THRESHOLD", "0.6"))


def update(settings: dict) -> None:
    """Apply a dict of setting overrides to this module's globals at runtime."""
    import server.config as _self
    bool_keys = {
        "NOTIFY_DESKTOP", "NOTIFY_ON_APPROVAL", "NOTIFY_ON_AUTO_PO",
        "NOTIFY_ON_SCORE_DROP", "NOTIFY_ON_DUPLICATE",
    }
    int_keys  = {"SMTP_PORT"}
    float_keys = {"SCORE_DROP_THRESHOLD"}
    for key, val in settings.items():
        if not hasattr(_self, key):
            continue
        if key in bool_keys:
            setattr(_self, key, bool(val))
        elif key in int_keys:
            setattr(_self, key, int(val))
        elif key in float_keys:
            setattr(_self, key, float(val))
        else:
            setattr(_self, key, str(val))
