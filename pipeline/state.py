import operator
from typing import Annotated, List, TypedDict


class PipelineState(TypedDict):
    # Raw data (filled by ingest)
    inventory: List[dict]
    suppliers: List[dict]
    all_pos: List[dict]
    open_pos: List[dict]
    invoices: List[dict]

    # Stage outputs
    detected: List[dict]    # DetectedCondition dicts
    evaluated: List[dict]   # EvaluatedItem dicts
    decisions: List[dict]   # Decision dicts
    actions: List[dict]     # ActionResult dicts

    # Final
    report: str
    errors: Annotated[List[str], operator.add]
