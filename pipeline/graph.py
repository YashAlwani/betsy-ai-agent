"""LangGraph pipeline definition."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import END, StateGraph

from pipeline.state import PipelineState
from pipeline.nodes import ingest, detect, evaluate, decide, act, audit


def build() -> "CompiledGraph":
    g = StateGraph(PipelineState)

    g.add_node("ingest",   ingest.node)
    g.add_node("detect",   detect.node)
    g.add_node("evaluate", evaluate.node)
    g.add_node("decide",   decide.node)
    g.add_node("act",      act.node)
    g.add_node("audit",    audit.node)

    g.set_entry_point("ingest")
    g.add_edge("ingest",   "detect")
    g.add_edge("detect",   "evaluate")
    g.add_edge("evaluate", "decide")
    g.add_edge("decide",   "act")
    g.add_edge("act",      "audit")
    g.add_edge("audit",    END)

    return g.compile()
