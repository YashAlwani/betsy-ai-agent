"""
Orchestra entry point.

Usage:
  python -m orchestra.run                              # full run, live API
  python -m orchestra.run --agent inventory_monitor   # test one agent
  python -m orchestra.run --agent supplier_scout
  python -m orchestra.run --agent invoice_auditor
  python -m orchestra.run --agent po_manager
  python -m orchestra.run --agent decision_logger
  python -m orchestra.run --scenario stockout_warning  # inject + full run
  python -m orchestra.run --scenario price_spike
  python -m orchestra.run --scenario duplicate_invoice
  python -m orchestra.run --scenario supplier_oos
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import api_client as api
from orchestra.graph import build

AGENT_MODULES = {
    "inventory_monitor": "orchestra.agents.inventory_monitor",
    "supplier_scout":    "orchestra.agents.supplier_scout",
    "invoice_auditor":   "orchestra.agents.invoice_auditor",
    "po_manager":        "orchestra.agents.po_manager",
    "decision_logger":   "orchestra.agents.decision_logger",
}


def run_full(scenario: str | None = None) -> dict:
    if scenario:
        print(f"\nInjecting scenario: {scenario}")
        api.inject_scenario(scenario)

    print("\n" + "=" * 60)
    print("ORCHESTRA -- Full run")
    print("=" * 60)

    graph = build()
    initial_state = {
        "brief": {},
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

    t0 = time.time()
    final = graph.invoke(initial_state)
    elapsed = time.time() - t0

    _print_results(final, elapsed)

    if scenario:
        api.reset_scenario()

    return final


def _print_results(state: dict, elapsed: float) -> None:
    print(f"\nTime: {elapsed:.1f}s")
    print(f"Errors: {state.get('errors', []) or 'none'}")

    brief = state.get("brief", {})
    print(f"\nData loaded: {len(brief.get('inventory', []))} SKUs, "
          f"{len(brief.get('invoices', []))} invoices, "
          f"{len(brief.get('suppliers', []))} suppliers")

    print(f"\nAgent findings:")
    print(f"  inventory_monitor : {len(state.get('inventory_findings', []))} finding(s)")
    print(f"  supplier_scout    : {len(state.get('supplier_findings', []))} finding(s)")
    print(f"  invoice_auditor   : {len(state.get('invoice_findings', []))} finding(s)")

    all_f = state.get("all_findings", [])
    print(f"\nAll findings ({len(all_f)}):")
    for f in all_f:
        print(f"  [{f['type'].upper()}] {f['severity']} -- SKU={f.get('sku_id', 'N/A')} "
              f"confidence={f.get('confidence', 0):.0%}")

    conflicts = state.get("conflicts", [])
    if conflicts:
        print(f"\nConflicts resolved ({len(conflicts)}):")
        for c in conflicts:
            print(f"  SKU={c['sku_id']}: {c['conflict'][0]} vs {c['conflict'][1]} → winner={c['winner']}")
    else:
        print("\nConflicts: none")

    decisions = state.get("decisions", [])
    print(f"\nDecisions ({len(decisions)}):")
    for d in decisions:
        label = "AUTO" if d.get("auto_approved") else "HUMAN"
        print(f"  [{d['action'].upper()}] {label} -- {d['reasoning'][:80]}")

    actions = state.get("actions", [])
    print(f"\nActions ({len(actions)}):")
    for a in actions:
        print(f"  [{a['action'].upper()}] {a['status']}")

    report = state.get("report", "")
    if report:
        print(f"\nReport:\n  {report}")
    print("=" * 60)


def run_agent(agent: str) -> None:
    module = AGENT_MODULES.get(agent)
    if not module:
        print(f"Unknown agent '{agent}'. Choose from: {', '.join(AGENT_MODULES)}")
        sys.exit(1)
    subprocess.run([sys.executable, "-m", module], check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Betsy Orchestra")
    parser.add_argument("--agent",    help="Test a single agent in isolation")
    parser.add_argument("--scenario", help="Inject a test scenario then run full orchestra")
    args = parser.parse_args()

    if args.agent:
        run_agent(args.agent)
    else:
        if not api.is_server_up():
            print(f"ERROR: API not reachable at {api.API_BASE}")
            print("Start with: uvicorn server.main:app --reload --port 8000")
            sys.exit(1)
        run_full(scenario=args.scenario)
