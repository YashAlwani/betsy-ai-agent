"""
Pipeline entry point.

Usage:
  python -m pipeline.run                          # full run, live API
  python -m pipeline.run --stage ingest           # test one stage
  python -m pipeline.run --stage detect
  python -m pipeline.run --stage evaluate
  python -m pipeline.run --stage decide
  python -m pipeline.run --stage act
  python -m pipeline.run --stage audit
  python -m pipeline.run --scenario stockout_warning   # inject + full run
  python -m pipeline.run --scenario price_spike
  python -m pipeline.run --scenario duplicate_invoice
  python -m pipeline.run --scenario supplier_oos
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import api_client as api
from pipeline.graph import build


STAGE_MODULES = {
    "ingest":   "pipeline.nodes.ingest",
    "detect":   "pipeline.nodes.detect",
    "evaluate": "pipeline.nodes.evaluate",
    "decide":   "pipeline.nodes.decide",
    "act":      "pipeline.nodes.act",
    "audit":    "pipeline.nodes.audit",
}


def run_full(scenario: str | None = None) -> dict:
    if scenario:
        print(f"\nInjecting scenario: {scenario}")
        api.inject_scenario(scenario)

    print("\n" + "=" * 60)
    print("PIPELINE -- Full run")
    print("=" * 60)

    graph = build()
    initial_state = {
        "inventory": [], "suppliers": [], "all_pos": [], "open_pos": [],
        "invoices": [], "detected": [], "evaluated": [], "decisions": [],
        "actions": [], "report": "", "errors": [],
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
    print(f"\nData loaded: {len(state.get('inventory', []))} SKUs, "
          f"{len(state.get('invoices', []))} invoices, "
          f"{len(state.get('suppliers', []))} suppliers")

    detected = state.get("detected", [])
    print(f"\nDetected ({len(detected)} conditions):")
    for c in detected:
        print(f"  [{c['type'].upper()}] {c['severity']} -- SKU={c.get('sku_id', 'N/A')}")

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


def run_stage(stage: str) -> None:
    """Delegate to the stage module's __main__ block."""
    module = STAGE_MODULES.get(stage)
    if not module:
        print(f"Unknown stage '{stage}'. Choose from: {', '.join(STAGE_MODULES)}")
        sys.exit(1)
    subprocess.run([sys.executable, "-m", module], check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Betsy Pipeline")
    parser.add_argument("--stage", help="Test a single stage in isolation")
    parser.add_argument("--scenario", help="Inject a test scenario then run full pipeline")
    args = parser.parse_args()

    if args.stage:
        run_stage(args.stage)
    else:
        if not api.is_server_up():
            print(f"ERROR: API not reachable at {api.API_BASE}")
            print("Start with: uvicorn server.main:app --reload --port 8000")
            sys.exit(1)
        run_full(scenario=args.scenario)
