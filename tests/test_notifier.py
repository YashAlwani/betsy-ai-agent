"""Tests for server/notifier.py

Run with:  python -m pytest tests/test_notifier.py -v

All tests use mocking so no real email or desktop APIs are called.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Make sure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset_config(**overrides):
    """Reload server.config with custom env-var state."""
    import importlib
    import server.config as cfg
    defaults = dict(
        NOTIFY_DESKTOP=True,
        NOTIFY_EMAIL="jenny@company.com",
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USER="betsy@company.com",
        SMTP_PASS="secret",
        NOTIFY_ON_APPROVAL=True,
        NOTIFY_ON_AUTO_PO=True,
        NOTIFY_ON_SCORE_DROP=True,
        NOTIFY_ON_DUPLICATE=True,
        SCORE_DROP_THRESHOLD=0.6,
    )
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(cfg, k, v)
    return cfg


# ── Desktop notification tests ────────────────────────────────────────────────

class TestDesktopNotification:
    def test_calls_plyer_when_desktop_enabled(self):
        cfg = _reset_config(NOTIFY_DESKTOP=True)
        mock_plyer = MagicMock()
        with patch.dict("sys.modules", {"plyer": mock_plyer, "plyer.notification": mock_plyer.notification}):
            import importlib, server.notifier as n
            importlib.reload(n)
            n._desktop("Test title", "Test message")
        mock_plyer.notification.notify.assert_called_once()
        kwargs = mock_plyer.notification.notify.call_args.kwargs
        assert kwargs["title"] == "Test title"
        assert kwargs["app_name"] == "Betsy AI"

    def test_noop_when_desktop_disabled(self):
        cfg = _reset_config(NOTIFY_DESKTOP=False)
        mock_plyer = MagicMock()
        with patch.dict("sys.modules", {"plyer": mock_plyer, "plyer.notification": mock_plyer.notification}):
            import importlib, server.notifier as n
            importlib.reload(n)
            n._desktop("Title", "Message")
        mock_plyer.notification.notify.assert_not_called()

    def test_truncates_message_to_256_chars(self):
        cfg = _reset_config(NOTIFY_DESKTOP=True)
        long_msg = "x" * 400
        mock_plyer = MagicMock()
        with patch.dict("sys.modules", {"plyer": mock_plyer, "plyer.notification": mock_plyer.notification}):
            import importlib, server.notifier as n
            importlib.reload(n)
            n._desktop("T", long_msg)
        sent = mock_plyer.notification.notify.call_args.kwargs["message"]
        assert len(sent) <= 256

    def test_swallows_plyer_exception(self):
        cfg = _reset_config(NOTIFY_DESKTOP=True)
        mock_plyer = MagicMock()
        mock_plyer.notification.notify.side_effect = RuntimeError("display not found")
        with patch.dict("sys.modules", {"plyer": mock_plyer, "plyer.notification": mock_plyer.notification}):
            import importlib, server.notifier as n
            importlib.reload(n)
            n._desktop("T", "M")  # must not raise


# ── Email notification tests ──────────────────────────────────────────────────

class TestEmailNotification:
    def test_email_worker_sends_correct_headers(self):
        _reset_config()
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            n._email_worker("Test subject", "<p>hello</p>")
        mock_smtp.sendmail.assert_called_once()
        args = mock_smtp.sendmail.call_args
        assert "betsy@company.com" in args[0]
        assert "jenny@company.com" in str(args[0])

    def test_email_noop_when_no_email_configured(self):
        cfg = _reset_config(NOTIFY_EMAIL="", SMTP_USER="")
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch("threading.Thread") as mock_thread:
            n._email("Subject", "<p>body</p>")
        mock_thread.assert_not_called()

    def test_email_noop_when_no_smtp_host(self):
        cfg = _reset_config(SMTP_HOST="")
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch("threading.Thread") as mock_thread:
            n._email("Subject", "<p>body</p>")
        mock_thread.assert_not_called()

    def test_email_spawns_daemon_thread(self):
        _reset_config()
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch("threading.Thread") as mock_thread:
            n._email("Subject", "<p>body</p>")
        mock_thread.assert_called_once()
        assert mock_thread.call_args.kwargs.get("daemon") is True

    def test_email_worker_swallows_smtp_exception(self):
        _reset_config()
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("no server")):
            n._email_worker("Subject", "<html></html>")  # must not raise


# ── Public notification function tests ────────────────────────────────────────

class TestNotifyApprovalRequired:
    def test_fires_when_toggle_on(self):
        _reset_config(NOTIFY_ON_APPROVAL=True)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email") as me:
            n.notify_approval_required({
                "action": "generate_po", "sku_id": "SKU-003",
                "supplier_id": "SUP-01", "po_total": 8597.0,
                "reasoning": "Critical stockout risk",
            })
        md.assert_called_once()
        me.assert_called_once()

    def test_noop_when_toggle_off(self):
        _reset_config(NOTIFY_ON_APPROVAL=False)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email") as me:
            n.notify_approval_required({"action": "generate_po", "sku_id": "SKU-003"})
        md.assert_not_called()
        me.assert_not_called()

    def test_action_label_mapping(self):
        _reset_config(NOTIFY_ON_APPROVAL=True)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email"):
            n.notify_approval_required({"action": "flag_duplicate", "sku_id": "SKU-004"})
        title = md.call_args[0][0]
        assert "SKU-004" in title


class TestNotifyScoreDrop:
    def test_fires_when_toggle_on(self):
        _reset_config(NOTIFY_ON_SCORE_DROP=True)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email") as me:
            n.notify_score_drop("QuickShip", 0.65, 0.55, "PO-001")
        md.assert_called_once()
        me.assert_called_once()

    def test_noop_when_toggle_off(self):
        _reset_config(NOTIFY_ON_SCORE_DROP=False)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email"):
            n.notify_score_drop("QuickShip", 0.65, 0.55, "PO-001")
        md.assert_not_called()

    def test_supplier_name_in_desktop_message(self):
        _reset_config(NOTIFY_ON_SCORE_DROP=True)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email"):
            n.notify_score_drop("FastParts", 0.70, 0.45, "PO-002")
        assert "FastParts" in md.call_args[0][0]


class TestNotifyAutoApproved:
    def test_fires_when_toggle_on(self):
        _reset_config(NOTIFY_ON_AUTO_PO=True)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email") as me:
            n.notify_auto_approved({
                "po_id": "PO-001", "sku_id": "SKU-001",
                "supplier_id": "SUP-01", "total_amount": 1200.0,
            })
        md.assert_called_once()
        me.assert_called_once()

    def test_noop_when_toggle_off(self):
        _reset_config(NOTIFY_ON_AUTO_PO=False)
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email"):
            n.notify_auto_approved({"po_id": "PO-001", "sku_id": "SKU-001"})
        md.assert_not_called()


class TestNotifyTest:
    def test_always_fires_desktop_and_email(self):
        _reset_config()
        import importlib, server.notifier as n
        importlib.reload(n)
        with patch.object(n, "_desktop") as md, patch.object(n, "_email") as me:
            n.notify_test()
        md.assert_called_once()
        me.assert_called_once()


# ── Config.update() tests ─────────────────────────────────────────────────────

class TestConfigUpdate:
    def test_updates_string_attr(self):
        import server.config as cfg
        cfg.NOTIFY_EMAIL = ""
        cfg.update({"NOTIFY_EMAIL": "new@example.com"})
        assert cfg.NOTIFY_EMAIL == "new@example.com"

    def test_updates_bool_attr(self):
        import server.config as cfg
        cfg.NOTIFY_ON_AUTO_PO = False
        cfg.update({"NOTIFY_ON_AUTO_PO": True})
        assert cfg.NOTIFY_ON_AUTO_PO is True

    def test_updates_int_attr(self):
        import server.config as cfg
        cfg.SMTP_PORT = 587
        cfg.update({"SMTP_PORT": 465})
        assert cfg.SMTP_PORT == 465

    def test_ignores_unknown_keys(self):
        import server.config as cfg
        original = cfg.NOTIFY_EMAIL
        cfg.update({"UNKNOWN_KEY": "whatever"})
        assert cfg.NOTIFY_EMAIL == original  # unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
