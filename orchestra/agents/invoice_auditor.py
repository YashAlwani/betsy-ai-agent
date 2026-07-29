"""
Orchestra Agent 3 -- Invoice Auditor
Detects duplicate invoices. LLM assesses fraud vs billing error.
Read-only: works entirely from the brief.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import call_json, get_llm
from orchestra.state import OrchestraState

AGENT_NAME = "invoice_auditor"


def run(brief: dict, llm=None) -> list:
    """Returns list of Finding dicts."""
    if llm is None:
        llm = get_llm()

    invoices = brief["invoices"]
    dupes    = _find_duplicates(invoices)
    findings = []

    for pair in dupes:
        result = call_json(
            llm,
            system=(
                "You are a financial auditor. Return ONLY valid JSON -- no markdown:\n"
                '{"risk_level": "HIGH|MEDIUM|LOW", '
                '"fraud_likelihood": "suspicious|likely_error|unknown", '
                '"confidence": 0.0-1.0, "reasoning": "..."}'
            ),
            user=(
                f"Duplicate invoice pair:\n"
                f"  Invoice A: {pair['invoice_1']}\n"
                f"  Invoice B: {pair['invoice_2']}\n"
                f"  Supplier: {pair['supplier_id']}\n"
                f"  Amount: ${pair['amount']}\n"
                f"  Days apart: {pair['days_apart']}\n\n"
                "Is this a billing error or potential fraud? Consider the time gap and amount."
            ),
        )

        if result.get("fallback"):
            risk            = "HIGH" if pair["days_apart"] <= 30 else "MEDIUM"
            fraud_likelihood = "unknown"
            confidence      = 1.0 if risk == "HIGH" else 0.7
            reasoning       = f"Rule-based: {pair['days_apart']} days apart"
        else:
            risk            = result.get("risk_level", "MEDIUM")
            fraud_likelihood = result.get("fraud_likelihood", "unknown")
            confidence      = float(result.get("confidence", 0.7))
            reasoning       = result.get("reasoning", "")

        findings.append({
            "agent": AGENT_NAME,
            "type": "duplicate_invoice",
            "severity": "warning",
            "sku_id": pair.get("sku_id"),
            "confidence": confidence,
            "data": {
                "invoice_1": pair["invoice_1"],
                "invoice_2": pair["invoice_2"],
                "newer_invoice": pair.get("newer_invoice"),
                "supplier_id": pair["supplier_id"],
                "amount": pair["amount"],
                "days_apart": pair["days_apart"],
                "risk_level": risk,
                "fraud_likelihood": fraud_likelihood,
            },
            "reasoning": reasoning,
            "recommendation": "flag_duplicate",
        })

    return findings


def _find_duplicates(invoices: list) -> list:
    # Disputed invoices are already handled — don't re-flag them every run.
    invoices = [inv for inv in invoices if inv.get("status") != "disputed"]
    dupes = []
    seen  = set()
    for i, a in enumerate(invoices):
        for j, b in enumerate(invoices):
            if i >= j:
                continue
            key = tuple(sorted([a["invoice_id"], b["invoice_id"]]))
            if key in seen:
                continue
            if a["supplier_id"] != b["supplier_id"]:
                continue
            if abs(a["total_amount"] - b["total_amount"]) > 0.01:
                continue
            try:
                d1 = datetime.fromisoformat(a["date"])
                d2 = datetime.fromisoformat(b["date"])
            except (ValueError, KeyError):
                continue
            days = abs((d1 - d2).days)
            if days > 60:
                continue
            seen.add(key)
            newer = a["invoice_id"] if d1 >= d2 else b["invoice_id"]
            dupes.append({
                "invoice_1": a["invoice_id"],
                "invoice_2": b["invoice_id"],
                "newer_invoice": newer,
                "supplier_id": a["supplier_id"],
                "sku_id": a.get("sku_id"),
                "amount": a["total_amount"],
                "days_apart": days,
            })
    return dupes


def node(state: OrchestraState) -> dict:
    try:
        llm = get_llm()
        findings = run(state["brief"], llm)
        return {"invoice_findings": findings}
    except Exception as exc:
        return {"errors": [f"{AGENT_NAME}: {exc}"], "invoice_findings": []}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import time
    from shared import api_client as api

    print("\n" + "=" * 60)
    print("ORCHESTRA -- Agent: invoice_auditor")
    print("=" * 60)

    offline = not api.is_server_up()
    brief = {
        "inventory": api.load_inventory() if offline else api.get_inventory(),
        "suppliers": api.load_suppliers() if offline else api.get_suppliers(),
        "all_pos":   api.load_purchase_orders() if offline else api.get_purchase_orders(),
        "invoices":  api.load_invoices() if offline else api.get_invoices(),
    }

    llm = get_llm()
    t0 = time.time()
    findings = run(brief, llm)
    elapsed = time.time() - t0

    print(f"Time: {elapsed:.1f}s | Findings: {len(findings)}\n")
    for f in findings:
        d = f["data"]
        print(f"  [DUPLICATE] {d['invoice_1']} & {d['invoice_2']}")
        print(f"    Amount: ${d['amount']} | Days apart: {d['days_apart']} | "
              f"Risk: {d['risk_level']} | Fraud: {d['fraud_likelihood']}")
        print(f"    Confidence: {f['confidence']:.0%}")
        print(f"    Reasoning: {f['reasoning'][:120]}")
        print()
    if not findings:
        print("  No duplicate invoices detected.")
    print("=" * 60)
