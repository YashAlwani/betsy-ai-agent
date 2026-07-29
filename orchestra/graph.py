"""LangGraph orchestra definition."""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import END, StateGraph

from orchestra.state import OrchestraState
from orchestra.agents import (
    inventory_monitor,
    supplier_scout,
    invoice_auditor,
    po_manager,
    decision_logger,
)
from shared import api_client as api
from shared.llm import call_json, get_llm

MAX_AUTO_USD = 5000.0

# ── Conflict precedence (code-level safety) ───────────────────────────────────
PRECEDENCE = {
    ("duplicate_invoice", "stockout_risk"):    "duplicate_invoice",
    ("price_spike",       "stockout_risk"):    "price_spike",
    ("supplier_unavailable", "stockout_risk"): "stockout_risk",
}


# ── Graph nodes ───────────────────────────────────────────────────────────────

def build_brief_node(state: OrchestraState) -> dict:
    """Fetch all data once. Build immutable brief for all agents.

    World data comes from a single consistent snapshot (can't be split across
    a tick boundary); suppliers come from Betsy's API so the brief carries her
    learned reliability scores rather than anything the world claims."""
    try:
        snapshot  = api.get_snapshot()
        suppliers = api.get_suppliers()
        all_pos   = snapshot["purchase_orders"]
        open_pos  = [po for po in all_pos if po.get("status") not in {"delivered", "cancelled"}]
        return {
            "brief": {
                "inventory": snapshot["inventory"],
                "suppliers": suppliers,
                "all_pos": all_pos,
                "open_pos": open_pos,
                "invoices": snapshot["invoices"],
                "clock": snapshot.get("clock", {}),
            },
            "inventory_findings": [],
            "supplier_findings": [],
            "invoice_findings": [],
            "all_findings": [],
            "conflicts": [],
            "decisions": [],
            "actions": [],
            "report": "",
            "errors": [],
        }
    except Exception as exc:
        return {"errors": [f"build_brief: {exc}"], "brief": {}}


def parallel_analysis_node(state: OrchestraState) -> dict:
    """Run inventory_monitor, supplier_scout, invoice_auditor in parallel threads."""
    brief = state["brief"]
    llm   = get_llm()
    results = {}

    agents = {
        "inventory_findings": lambda: inventory_monitor.run(brief, llm),
        "supplier_findings":  lambda: supplier_scout.run(brief, llm),
        "invoice_findings":   lambda: invoice_auditor.run(brief, llm),
    }

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn): key for key, fn in agents.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result(timeout=60)
            except Exception as exc:
                results[key] = []
                results.setdefault("errors", []).append(f"{key}: {exc}")

    all_findings = (
        results.get("inventory_findings", [])
        + results.get("supplier_findings", [])
        + results.get("invoice_findings", [])
    )
    return {
        "inventory_findings": results.get("inventory_findings", []),
        "supplier_findings":  results.get("supplier_findings", []),
        "invoice_findings":   results.get("invoice_findings", []),
        "all_findings":       all_findings,
        "errors":             results.get("errors", []),
    }


def orchestrate_node(state: OrchestraState) -> dict:
    """Resolve conflicts between agent findings and produce decisions."""
    llm      = get_llm()
    findings = state["all_findings"]
    brief    = state["brief"]

    # Group findings by sku_id
    by_sku: dict = {}
    for f in findings:
        by_sku.setdefault(f.get("sku_id"), []).append(f)

    conflicts  = []
    decisions  = []

    for sku_id, sku_findings in by_sku.items():
        action_types = [f["type"] for f in sku_findings]

        # Detect conflict
        conflict_pair = None
        for a_type in action_types:
            for b_type in action_types:
                if a_type != b_type:
                    key = tuple(sorted([a_type, b_type]))
                    if key in {tuple(sorted(k)) for k in PRECEDENCE}:
                        conflict_pair = (a_type, b_type)
                        break

        if conflict_pair:
            winner_type = _resolve_conflict(conflict_pair, sku_findings, llm)
            a_f = next(f for f in sku_findings if f["type"] == conflict_pair[0])
            b_f = next(f for f in sku_findings if f["type"] == conflict_pair[1])
            conflicts.append({
                "sku_id": sku_id,
                "conflict": conflict_pair,
                "winner": winner_type,
                "findings": [a_f, b_f],
            })
            winning_findings = [f for f in sku_findings if f["type"] == winner_type]
        else:
            winning_findings = sku_findings

        for f in winning_findings:
            decisions.append(_finding_to_decision(f, brief))

    return {"conflicts": conflicts, "decisions": decisions}


def _resolve_conflict(pair: tuple, findings: list, llm) -> str:
    a, b = pair
    key  = tuple(sorted([a, b]))
    for pk, winner in PRECEDENCE.items():
        if tuple(sorted(pk)) == key:
            return winner

    # LLM tiebreaker
    fa = next((f for f in findings if f["type"] == a), {})
    fb = next((f for f in findings if f["type"] == b), {})
    result = call_json(
        llm,
        system=(
            "You are a procurement orchestrator. Return ONLY valid JSON -- no markdown:\n"
            '{"winner": "<finding_type>", "reasoning": "..."}\n'
            "Safety rules: duplicate_invoice always blocks PO creation. "
            "price_spike always requires human approval before ordering."
        ),
        user=(
            f"Conflicting findings for the same SKU:\n"
            f"Finding A: type={a}, severity={fa.get('severity')}, confidence={fa.get('confidence')}\n"
            f"Finding B: type={b}, severity={fb.get('severity')}, confidence={fb.get('confidence')}\n\n"
            "Which finding should take priority?"
        ),
    )
    if not result.get("fallback"):
        return result.get("winner", a)
    # Fallback: higher severity wins
    sev = {"critical": 2, "warning": 1, "info": 0}
    return a if sev.get(fa.get("severity", "info"), 0) >= sev.get(fb.get("severity", "info"), 0) else b


def _finding_to_decision(finding: dict, brief: dict) -> dict:
    ftype = finding["type"]

    if ftype == "duplicate_invoice":
        return {
            "action": "flag_duplicate",
            "requires_human": True,
            "auto_approved": False,
            "confidence": finding["confidence"],
            "reasoning": finding["reasoning"],
            "finding": finding,
        }

    if ftype == "price_spike":
        return {
            "action": "flag_for_approval",
            "requires_human": True,
            "auto_approved": False,
            "confidence": 0.0,
            "reasoning": finding["reasoning"],
            "finding": finding,
        }

    if ftype == "supplier_unavailable":
        return {
            "action": "escalate",
            "requires_human": True,
            "auto_approved": False,
            "confidence": finding["confidence"],
            "reasoning": finding["reasoning"],
            "finding": finding,
        }

    if ftype == "stockout_risk":
        # Find matching supplier recommendation from supplier_scout
        sku_id   = finding.get("sku_id")
        sup_data = _get_supplier_data(sku_id, brief)
        rec      = sup_data.get("recommended_supplier") or {}
        inv_item = next((i for i in brief["inventory"] if i["sku_id"] == sku_id), {})
        qty      = inv_item.get("max_stock", 0) - inv_item.get("current_stock", 0)
        price    = rec.get("unit_price", 0)
        po_total = qty * price
        requires_human = po_total > MAX_AUTO_USD or not rec

        enriched = dict(finding)
        enriched["supplier_data"] = sup_data

        return {
            "action": "generate_po",
            "requires_human": requires_human,
            "auto_approved": not requires_human,
            "confidence": finding["confidence"],
            "reasoning": finding["reasoning"],
            "po_total": po_total,
            "finding": enriched,
        }

    return {
        "action": "no_action",
        "requires_human": False,
        "auto_approved": True,
        "confidence": 0.5,
        "reasoning": f"No decision rule for finding type: {ftype}",
        "finding": finding,
    }


def _get_supplier_data(sku_id: str, brief: dict) -> dict:
    """Build best supplier recommendation for a SKU from the brief."""
    suppliers = brief.get("suppliers", [])
    options = [
        {
            "supplier_id": s["supplier_id"],
            "name": s["name"],
            "score": round(s["reliability_score"] / max(s["catalog"][sku_id]["lead_days"], 0.1), 3),
            "unit_price": s["catalog"][sku_id]["unit_price"],
            "lead_days": s["catalog"][sku_id]["lead_days"],
            "available": s["availability"],
        }
        for s in suppliers
        if s["availability"] and sku_id in s.get("catalog", {})
    ]
    if not options:
        return {}
    options.sort(key=lambda x: x["score"], reverse=True)
    return {"recommended_supplier": options[0], "all_options": options}


def execute_node(state: OrchestraState) -> dict:
    """PO Manager executes auto-approved decisions serially."""
    try:
        actions = po_manager.run(state["decisions"], state["brief"])
        return {"actions": actions}
    except Exception as exc:
        return {"errors": [f"execute: {exc}"], "actions": []}


def audit_node(state: OrchestraState) -> dict:
    """Decision Logger writes audit. Always runs."""
    try:
        llm    = get_llm()
        report = decision_logger.run(dict(state), llm)
        return {"report": report}
    except Exception as exc:
        return {"errors": [f"audit: {exc}"], "report": "Audit failed."}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build() -> "CompiledGraph":
    g = StateGraph(OrchestraState)

    g.add_node("build_brief",        build_brief_node)
    g.add_node("parallel_analysis",  parallel_analysis_node)
    g.add_node("orchestrate",        orchestrate_node)
    g.add_node("execute",            execute_node)
    g.add_node("audit",              audit_node)

    g.set_entry_point("build_brief")
    g.add_edge("build_brief",       "parallel_analysis")
    g.add_edge("parallel_analysis", "orchestrate")
    g.add_edge("orchestrate",       "execute")
    g.add_edge("execute",           "audit")
    g.add_edge("audit",             END)

    return g.compile()
