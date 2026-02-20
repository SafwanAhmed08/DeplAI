from __future__ import annotations

from agentic_layer.scan_graph.layer6_subagents.generic_category_runner import run_generic_category
from agentic_layer.scan_graph.state import ScanState


OWASP_A1 = "A01:2021-Broken Access Control"


def run_owasp_a1(state: ScanState) -> list[dict]:
    enriched = run_generic_category(state, OWASP_A1)
    for item in enriched:
        item["subagent"] = "owasp_a1"
        item["control_focus"] = "access_control"
    return enriched
