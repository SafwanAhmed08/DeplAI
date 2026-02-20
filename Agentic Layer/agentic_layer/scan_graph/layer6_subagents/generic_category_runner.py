from __future__ import annotations

from agentic_layer.scan_graph.state import ScanState


def run_generic_category(state: ScanState, category: str) -> list[dict]:
    category_findings = state["owasp_mapped"].get(category, [])
    enriched: list[dict] = []
    for finding in category_findings:
        enriched.append(
            {
                **finding,
                "layer": "layer6",
                "category": category,
                "subagent": "generic_category_runner",
                "enrichment": "category_validation_pass",
            }
        )
    return enriched
