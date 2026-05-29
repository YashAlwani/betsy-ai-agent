import operator
from typing import Annotated, List, TypedDict


class OrchestraState(TypedDict):
    # Situation brief -- filled by build_brief node
    brief: dict   # {inventory, suppliers, all_pos, open_pos, invoices}

    # Agent findings -- filled by each analysis agent
    inventory_findings: List[dict]
    supplier_findings: List[dict]
    invoice_findings: List[dict]

    # Orchestration output
    all_findings: List[dict]
    conflicts: List[dict]
    decisions: List[dict]
    actions: List[dict]

    # Final
    report: str
    errors: Annotated[List[str], operator.add]
