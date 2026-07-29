"""
Run both architectures against all 4 test scenarios and print a side-by-side report.

Each scenario is injected as an event script into a freshly reset world, the
clock is stepped once to apply it, and then each graph runs against the result.

Usage (both services must be running):
  python compare.py
  python compare.py --scenario stockout_warning   # single scenario
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from shared import api_client as api
from shared import world_client
from pipeline.graph import build as build_pipeline
from orchestra.graph import build as build_orchestra


def _setup_scenario(scenario: str) -> None:
    world_client.reset_world()
    world_client.pause()
    world_client.inject_script(scenario)
    world_client.step(1)  # apply the script's events

SCENARIOS = ["stockout_warning", "price_spike", "duplicate_invoice", "supplier_oos"]

EXPECTED = {
    "stockout_warning":   "generate_po",
    "price_spike":        "flag_for_approval",
    "duplicate_invoice":  "flag_duplicate",
    "supplier_oos":       "generate_po",
}


def run_pipeline_scenario(scenario: str) -> dict:
    _setup_scenario(scenario)
    graph = build_pipeline()
    initial = {
        "inventory": [], "suppliers": [], "all_pos": [], "open_pos": [],
        "invoices": [], "detected": [], "evaluated": [], "decisions": [],
        "actions": [], "report": "", "errors": [],
    }
    t0    = time.time()
    state = graph.invoke(initial)
    elapsed = time.time() - t0
    world_client.reset_world()

    decisions = state.get("decisions", [])
    action    = decisions[0]["action"] if decisions else "no_action"
    return {
        "action":    action,
        "decisions": decisions,
        "detected":  state.get("detected", []),
        "errors":    state.get("errors", []),
        "time":      round(elapsed, 1),
        "report":    state.get("report", ""),
    }


def run_orchestra_scenario(scenario: str) -> dict:
    _setup_scenario(scenario)
    graph = build_orchestra()
    initial = {
        "brief": {}, "inventory_findings": [], "supplier_findings": [],
        "invoice_findings": [], "all_findings": [], "conflicts": [],
        "decisions": [], "actions": [], "report": "", "errors": [],
    }
    t0    = time.time()
    state = graph.invoke(initial)
    elapsed = time.time() - t0
    world_client.reset_world()

    decisions = state.get("decisions", [])
    action    = decisions[0]["action"] if decisions else "no_action"
    return {
        "action":    action,
        "decisions": decisions,
        "findings":  state.get("all_findings", []),
        "conflicts": state.get("conflicts", []),
        "errors":    state.get("errors", []),
        "time":      round(elapsed, 1),
        "report":    state.get("report", ""),
    }


def compare(scenarios: list) -> None:
    print("\n" + "=" * 70)
    print("BETSY -- Architecture Comparison")
    print("Pipeline vs Orchestra | Ollama mistral")
    print("=" * 70)

    results = []

    for scenario in scenarios:
        expected = EXPECTED.get(scenario, "?")
        print(f"\n{'─' * 70}")
        print(f"Scenario: {scenario}  (expected: {expected})")
        print(f"{'─' * 70}")

        print("  Running pipeline...", end=" ", flush=True)
        try:
            p = run_pipeline_scenario(scenario)
            p_pass = p["action"] == expected
            print(f"done ({p['time']}s)")
        except Exception as exc:
            p = {"action": "ERROR", "time": 0, "errors": [str(exc)],
                 "decisions": [], "detected": [], "report": ""}
            p_pass = False
            print(f"ERROR: {exc}")

        print("  Running orchestra...", end=" ", flush=True)
        try:
            o = run_orchestra_scenario(scenario)
            o_pass = o["action"] == expected
            print(f"done ({o['time']}s)")
        except Exception as exc:
            o = {"action": "ERROR", "time": 0, "errors": [str(exc)],
                 "decisions": [], "findings": [], "conflicts": [], "report": ""}
            o_pass = False
            print(f"ERROR: {exc}")

        # Side-by-side summary
        p_mark = "PASS PASS" if p_pass else "FAIL FAIL"
        o_mark = "PASS PASS" if o_pass else "FAIL FAIL"

        print(f"\n  {'':20} {'PIPELINE':25} {'ORCHESTRA':25}")
        print(f"  {'Result':20} {p_mark + ' (' + p['action'] + ')':25} {o_mark + ' (' + o['action'] + ')':25}")
        print(f"  {'Time':20} {str(p['time']) + 's':25} {str(o['time']) + 's':25}")
        print(f"  {'Conditions found':20} {str(len(p.get('detected', []))):25} {str(len(o.get('findings', []))):25}")
        print(f"  {'Decisions made':20} {str(len(p.get('decisions', []))):25} {str(len(o.get('decisions', []))):25}")
        print(f"  {'Conflicts':20} {'N/A':25} {str(len(o.get('conflicts', []))):25}")
        p_err = len(p.get("errors", []))
        o_err = len(o.get("errors", []))
        print(f"  {'Errors':20} {str(p_err):25} {str(o_err):25}")

        if p.get("report"):
            print(f"\n  Pipeline report:   {p['report'][:100]}")
        if o.get("report"):
            print(f"  Orchestra report:  {o['report'][:100]}")

        results.append({
            "scenario":  scenario,
            "expected":  expected,
            "pipeline":  {"action": p["action"], "pass": p_pass, "time": p["time"]},
            "orchestra": {"action": o["action"], "pass": o_pass, "time": o["time"]},
        })

    # Final summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    p_total = sum(1 for r in results if r["pipeline"]["pass"])
    o_total = sum(1 for r in results if r["orchestra"]["pass"])
    p_time  = sum(r["pipeline"]["time"] for r in results)
    o_time  = sum(r["orchestra"]["time"] for r in results)

    print(f"{'':25} {'PIPELINE':20} {'ORCHESTRA':20}")
    print(f"{'Pass rate':25} {f'{p_total}/{len(results)}':20} {f'{o_total}/{len(results)}':20}")
    print(f"{'Total time':25} {f'{p_time:.1f}s':20} {f'{o_time:.1f}s':20}")
    print()
    for r in results:
        pm = "PASS" if r["pipeline"]["pass"]  else "FAIL"
        om = "PASS" if r["orchestra"]["pass"] else "FAIL"
        print(f"  {r['scenario']:30} pipeline={pm}  orchestra={om}  (expected: {r['expected']})")

    print(f"\n{'=' * 70}")
    print("Recommendation:")
    if p_total == o_total:
        print("  Both architectures produced the same results.")
        print("  → Use Pipeline for simpler audit trail.")
        print("  → Use Orchestra when you need parallel agents or explicit conflict logs.")
    elif p_total > o_total:
        print(f"  Pipeline passed more scenarios ({p_total} vs {o_total}).")
        print("  → Investigate orchestra conflicts/errors above.")
    else:
        print(f"  Orchestra passed more scenarios ({o_total} vs {p_total}).")
        print("  → Investigate pipeline decision logic above.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Pipeline vs Orchestra")
    parser.add_argument("--scenario", help="Run a single scenario instead of all four")
    args = parser.parse_args()

    if not api.is_server_up() or not world_client.is_up():
        print("ERROR: both services must be running.")
        print("Start with: python run_world.py  and  python run_server.py")
        sys.exit(1)

    scenarios = [args.scenario] if args.scenario else SCENARIOS
    compare(scenarios)
