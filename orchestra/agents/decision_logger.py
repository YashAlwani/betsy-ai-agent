"""
Orchestra Agent 5 -- Decision Logger
Writes audit entries. LLM generates plain-English narrative.
Always runs last.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from shared.llm import call_text, get_llm
from orchestra.state import OrchestraState

AGENT_NAME = "decision_logger"


def run(state: dict, llm=None) -> str:
    """Write audit entries and return narrative string."""
    if llm is None:
        llm = get_llm()

    findings  = state.get("all_findings", [])
    conflicts = state.get("conflicts", [])
    decisions = state.get("decisions", [])
    actions   = state.get("actions", [])

    f_summary  = ", ".join(f"{f['type']}({f['severity']})" for f in findings) or "none"
    c_summary  = f"{len(conflicts)} conflict(s) resolved" if conflicts else "no conflicts"
    d_summary  = ", ".join(f"{d['action']}({'auto' if d.get('auto_approved') else 'human'})" for d in decisions) or "none"
    a_summary  = ", ".join(f"{a['action']}:{a['status']}" for a in actions) or "none"

    narrative = call_text(
        llm,
        system="Summarize this procurement agent run in 2-3 sentences. Be factual. No markdown.",
        user=(
            f"Agents ran: inventory_monitor, supplier_scout, invoice_auditor, po_manager\n"
            f"Findings: {f_summary}\n"
            f"Conflicts: {c_summary}\n"
            f"Decisions: {d_summary}\n"
            f"Actions: {a_summary}"
        ),
    )

    api.log_decision(
        trigger="orchestra_run",
        analysis=f"Findings: {f_summary} | {c_summary}",
        decision=f"Decisions: {d_summary}",
        confidence=_avg_confidence(decisions),
        metadata={
            "findings": findings,
            "conflicts": conflicts,
            "decisions": [{k: v for k, v in d.items() if k != "finding"} for d in decisions],
            "actions": actions,
            "narrative": narrative,
        },
    )

    return narrative


def _avg_confidence(decisions: list) -> float:
    if not decisions:
        return 0.0
    return round(sum(d.get("confidence", 0) for d in decisions) / len(decisions), 2)


def node(state: OrchestraState) -> dict:
    try:
        llm = get_llm()
        report = run(dict(state), llm)
        return {"report": report}
    except Exception as exc:
        return {"errors": [f"{AGENT_NAME}: {exc}"], "report": "Audit failed."}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ORCHESTRA -- Agent: decision_logger")
    print("=" * 60)
    print("Decision logger summarises a completed run.")
    print("Running with a mock state to test the LLM narrative:\n")

    mock_state = {
        "all_findings": [
            {"type": "stockout_risk", "severity": "critical", "sku_id": "SKU-003"},
            {"type": "duplicate_invoice", "severity": "warning", "sku_id": "SKU-004"},
        ],
        "conflicts": [],
        "decisions": [
            {"action": "generate_po", "auto_approved": False, "confidence": 0.85},
            {"action": "flag_duplicate", "auto_approved": False, "confidence": 1.0},
        ],
        "actions": [
            {"action": "generate_po", "status": "pending_human_review"},
            {"action": "flag_duplicate", "status": "logged"},
        ],
    }

    llm = get_llm()
    narrative = run(mock_state, llm)
    print(f"Narrative:\n  {narrative}")
    print("=" * 60)
