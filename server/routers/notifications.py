from fastapi import APIRouter

from server import config, notifier

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/config")
def get_notification_config():
    """Return current notification configuration (no secrets exposed)."""
    return {
        "desktop_enabled":   config.NOTIFY_DESKTOP,
        "email_configured":  bool(config.NOTIFY_EMAIL and config.SMTP_USER and config.SMTP_HOST),
        "notify_to":         config.NOTIFY_EMAIL or None,
        "triggers": {
            "approval_required": config.NOTIFY_ON_APPROVAL,
            "auto_approved_po":  config.NOTIFY_ON_AUTO_PO,
            "score_drop":        config.NOTIFY_ON_SCORE_DROP,
            "duplicate_invoice": config.NOTIFY_ON_DUPLICATE,
        },
        "score_drop_threshold": config.SCORE_DROP_THRESHOLD,
    }


@router.post("/config")
def update_notification_config(settings: dict):
    """Update notification settings at runtime (survives until server restart).
    To persist across restarts, set the corresponding env vars in .env.
    """
    # Map from UI-friendly keys to config module attribute names
    key_map = {
        "NOTIFY_EMAIL":        "NOTIFY_EMAIL",
        "SMTP_HOST":           "SMTP_HOST",
        "SMTP_PORT":           "SMTP_PORT",
        "SMTP_USER":           "SMTP_USER",
        "SMTP_PASS":           "SMTP_PASS",
        "NOTIFY_ON_APPROVAL":  "NOTIFY_ON_APPROVAL",
        "NOTIFY_ON_AUTO_PO":   "NOTIFY_ON_AUTO_PO",
        "NOTIFY_ON_SCORE_DROP":"NOTIFY_ON_SCORE_DROP",
        "NOTIFY_ON_DUPLICATE": "NOTIFY_ON_DUPLICATE",
        "SCORE_DROP_THRESHOLD":"SCORE_DROP_THRESHOLD",
    }
    mapped = {key_map[k]: v for k, v in settings.items() if k in key_map}
    config.update(mapped)
    return {"status": "updated", "applied": list(mapped.keys())}


@router.post("/test")
def send_test_notification():
    """Trigger a test notification through all configured channels."""
    notifier.notify_test()
    return {
        "status":   "dispatched",
        "channels": {
            "desktop": config.NOTIFY_DESKTOP,
            "email":   bool(config.NOTIFY_EMAIL and config.SMTP_USER),
        },
    }
