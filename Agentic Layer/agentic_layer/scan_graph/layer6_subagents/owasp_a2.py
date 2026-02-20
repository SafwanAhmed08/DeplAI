from __future__ import annotations

from agentic_layer.scan_graph.layer6_subagents.generic_category_runner import run_generic_category
from agentic_layer.scan_graph.state import ScanState


OWASP_A2 = "A02:2021-Cryptographic Failures"


def run_owasp_a2(state: ScanState) -> list[dict]:
    enriched = run_generic_category(state, OWASP_A2)
    for item in enriched:
        item["subagent"] = "owasp_a2"
        item["control_focus"] = "cryptography"
    return enriched
