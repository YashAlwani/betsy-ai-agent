"""Stage 6 -- write run summary. LLM generates plain-English narrative."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared import api_client as api
from shared.llm import call_text, get_llm
from pipeline.state import PipelineState


def run(detected: list, decisions: list, actions: list, llm=None) -> dict:
    if llm is None:
        llm = get_llm()

    condition_summary = ", ".join(
        f"{c['type']}({c['severity']})" for c in detected
    ) or "none"

    decision_summary = ", ".join(
        f"{d['action']}({'auto' if d.get('auto_approved') else 'human'})"
        for d in decisions
    ) or "none"

    action_summary = ", ".join(
        f"{a['action']}:{a['status']}" for a in actions
    ) or "none"

    narrative = call_text(
        llm,
        system="Summarize this procurement agent run in 2-3 sentences. Be factual and concise. No markdown.",
        user=(
            f"Conditions detected: {condition_summary}\n"
            f"Decisions made: {decision_summary}\n"
            f"Actions taken: {action_summary}"
        ),
    )

    api.log_decision(
        trigger="pipeline_run",
        analysis=f"Detected: {condition_summary}",
        decision=f"Decided: {decision_summary}",
        confidence=_avg_confidence(decisions),
        metadata={
            "conditions": detected,
            "decisions": _strip_item(decisions),
            "actions": actions,
            "narrative": narrative,
        },
    )

    return {"report": narrative}


def node(state: PipelineState) -> dict:
    try:
        llm = get_llm()
        return run(state["detected"], state["decisions"], state["actions"], llm)
    except Exception as exc:
        return {"errors": [f"audit: {exc}"], "report": "Audit failed."}


def _avg_confidence(decisions: list) -> float:
    if not decisions:
        return 0.0
    return round(sum(d.get("confidence", 0) for d in decisions) / len(decisions), 2)


def _strip_item(decisions: list) -> list:
    """Remove nested item (contains suppliers list) to keep log payload small."""
    return [{k: v for k, v in d.items() if k != "item"} for d in decisions]


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from shared import api_client as api
    from pipeline.nodes.detect import run as detect_run
    from pipeline.nodes.evaluate import run as evaluate_run
    from pipeline.nodes.decide import run as decide_run
    from pipeline.nodes.act import run as act_run
    from shared.llm import get_llm

    print("\n" + "=" * 60)
    print("PIPELINE -- Stage: audit")
    print("=" * 60)

    offline = not api.is_server_up()
    inventory = api.load_inventory() if offline else api.get_inventory()
    suppliers = api.load_suppliers() if offline else api.get_suppliers()
    all_pos   = api.load_purchase_orders() if offline else api.get_purchase_orders()
    invoices  = api.load_invoices() if offline else api.get_invoices()

    llm = get_llm()
    detected  = detect_run(inventory, suppliers, all_pos, invoices)["detected"]
    evaluated = evaluate_run(detected, suppliers, llm)["evaluated"]
    decisions = decide_run(evaluated, llm)["decisions"]
    actions   = act_run(decisions)["actions"]

    result = run(detected, decisions, actions, llm)
    print("\nNarrative:")
    print(f"  {result['report']}")
    print("=" * 60)
