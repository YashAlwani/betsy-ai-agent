"""Desktop and email notification dispatch for Betsy.

All public functions are fire-and-forget: they return immediately and never
raise exceptions, so a notification failure cannot break the agent's execution.
Email is sent in a background thread; desktop calls are synchronous but
wrapped in try/except.
"""
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from server import config

# ── Internal send helpers ─────────────────────────────────────────────────────

def _desktop(title: str, message: str) -> None:
    if not config.NOTIFY_DESKTOP:
        return
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:256],
            app_name="Betsy AI",
            timeout=10,
        )
    except Exception:
        pass


def _email(subject: str, html: str) -> None:
    if not (config.NOTIFY_EMAIL and config.SMTP_USER and config.SMTP_HOST):
        return
    threading.Thread(target=_email_worker, args=(subject, html), daemon=True).start()


def _email_worker(subject: str, html: str) -> None:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Betsy] {subject}"
        msg["From"]    = config.SMTP_USER
        msg["To"]      = config.NOTIFY_EMAIL
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(config.SMTP_USER, config.SMTP_PASS)
            srv.sendmail(config.SMTP_USER, [config.NOTIFY_EMAIL], msg.as_string())
    except Exception:
        pass


def _html_wrap(title: str, colour: str, rows: list[tuple[str, str]]) -> str:
    """Minimal responsive HTML email that matches Betsy's design language."""
    rows_html = "".join(
        f"<tr><td style='padding:6px 0;color:#64748b;font-size:13px;width:38%'>{k}</td>"
        f"<td style='padding:6px 0;font-size:13px;font-weight:600'>{v}</td></tr>"
        for k, v in rows
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px">
<table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden">
  <tr><td style="background:{colour};padding:20px 28px">
    <span style="color:#fff;font-size:18px;font-weight:800">✦ Betsy</span>
    <span style="color:rgba(255,255,255,0.75);font-size:13px;margin-left:10px">AI Procurement Layer</span>
  </td></tr>
  <tr><td style="padding:24px 28px">
    <h2 style="margin:0 0 16px;font-size:16px;color:#0f172a">{title}</h2>
    <table width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
  </td></tr>
  <tr><td style="padding:16px 28px;background:#f8fafc;border-top:1px solid #e2e8f0">
    <a href="http://localhost:8000/betsy" style="color:#7c3aed;font-size:12px;text-decoration:none">
      Open Betsy dashboard →
    </a>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""


# ── Public notification functions ─────────────────────────────────────────────

def notify_approval_required(item: dict) -> None:
    """Fire when any decision is queued for human review."""
    if not config.NOTIFY_ON_APPROVAL:
        return

    sku      = item.get("sku_id", "Unknown SKU")
    supplier = item.get("supplier_id", "Unknown supplier")
    total    = item.get("po_total") or 0
    action   = item.get("action", "review")
    reason   = (item.get("reasoning") or "")[:160]

    action_label = {
        "generate_po":       "Purchase order",
        "flag_duplicate":    "Duplicate invoice flagged",
        "flag_for_approval": "Price spike",
        "escalate":          "Supplier unavailable",
    }.get(action, action.replace("_", " ").title())

    desktop_msg = (
        f"{action_label}: {sku}\n"
        f"{f'Supplier: {supplier}  |  ' if supplier else ''}"
        f"{f'Total: €{total:,.0f}' if total else ''}\n"
        f"{reason}"
    )
    _desktop(f"Betsy needs your OK — {sku}", desktop_msg.strip())

    html = _html_wrap(
        title=f"Approval needed — {action_label}",
        colour="#d97706",
        rows=[
            ("Item", sku),
            ("Supplier", supplier),
            ("Total", f"€{total:,.2f}" if total else "—"),
            ("Betsy's reasoning", reason or "—"),
            ("Action required", action_label),
        ],
    )
    _email(f"Approval needed — {sku}", html)


def notify_auto_approved(po: dict) -> None:
    """Fire when Betsy autonomously creates a PO without human intervention."""
    if not config.NOTIFY_ON_AUTO_PO:
        return

    po_id    = po.get("po_id", "")
    sku      = po.get("sku_id", "")
    supplier = po.get("supplier_id", "")
    total    = po.get("total_amount") or 0

    _desktop(
        f"Betsy auto-ordered — {sku}",
        f"PO {po_id} placed with {supplier}\nTotal: €{total:,.0f}",
    )
    html = _html_wrap(
        title="Betsy placed an order automatically",
        colour="#7c3aed",
        rows=[
            ("PO ID",    po_id),
            ("Item",     sku),
            ("Supplier", supplier),
            ("Total",    f"€{total:,.2f}"),
            ("Status",   "Auto-approved — no action needed"),
        ],
    )
    _email(f"Auto-approved PO — {sku}", html)


def notify_score_drop(supplier_name: str, old_score: float, new_score: float, po_id: str) -> None:
    """Fire when a supplier's EMA reliability score falls below the threshold."""
    if not config.NOTIFY_ON_SCORE_DROP:
        return

    msg = (
        f"{supplier_name} score dropped: {old_score:.2f} → {new_score:.2f}\n"
        f"Below warning threshold ({config.SCORE_DROP_THRESHOLD:.2f}). "
        f"Late delivery on PO {po_id}."
    )
    _desktop(f"Supplier alert — {supplier_name}", msg)

    html = _html_wrap(
        title=f"Supplier reliability warning — {supplier_name}",
        colour="#dc2626",
        rows=[
            ("Supplier",   supplier_name),
            ("Old score",  f"{old_score:.4f}"),
            ("New score",  f"{new_score:.4f}  ⬇"),
            ("Threshold",  f"{config.SCORE_DROP_THRESHOLD:.2f}"),
            ("Triggered by", f"Late delivery on PO {po_id}"),
            ("What this means", "Betsy will rank this supplier lower on future orders"),
        ],
    )
    _email(f"Supplier score warning — {supplier_name}", html)


def notify_duplicate_invoice(invoice_1: str, invoice_2: str,
                             supplier_id: str, amount: float, days_apart: int) -> None:
    """Fire when a duplicate invoice pair is flagged — re-uses the approval trigger."""
    if not config.NOTIFY_ON_DUPLICATE:
        return

    msg = (
        f"Possible duplicate invoice from {supplier_id}\n"
        f"{invoice_1} & {invoice_2} — €{amount:,.2f} — {days_apart} days apart"
    )
    _desktop("Betsy flagged a duplicate invoice", msg)

    html = _html_wrap(
        title="Duplicate invoice detected",
        colour="#dc2626",
        rows=[
            ("Supplier",     supplier_id),
            ("Invoice 1",    invoice_1),
            ("Invoice 2",    invoice_2),
            ("Amount each",  f"€{amount:,.2f}"),
            ("Days apart",   str(days_apart)),
            ("Next step",    "Review both invoices and approve or decline in Betsy"),
        ],
    )
    _email(f"Duplicate invoice — {supplier_id}", html)


def notify_test() -> None:
    """Send a test notification through all configured channels."""
    _desktop(
        "Betsy — test notification",
        "Desktop notifications are working. You'll see this when Betsy needs attention.",
    )
    html = _html_wrap(
        title="Test notification",
        colour="#7c3aed",
        rows=[
            ("Status",  "Notifications are configured correctly"),
            ("Desktop", "Enabled" if config.NOTIFY_DESKTOP else "Disabled"),
            ("Email",   config.NOTIFY_EMAIL or "Not configured"),
        ],
    )
    _email("Test notification — everything is working", html)
