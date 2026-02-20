from __future__ import annotations

from agentic_layer.shared.owasp_mapper import map_category_hint
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def owasp_mapper_node(state: ScanState) -> ScanState:
    # OWASP mapper groups normalized findings into OWASP categories.
    log_agent(state["scan_id"], "OWASPMapper", "Mapping findings to OWASP categories")

    mapped: dict[str, list[dict]] = {}
    for finding in state["findings"]:
        hint = finding.get("category_hint", "security_misconfiguration")
        category = map_category_hint(str(hint))
        mapped.setdefault(category, []).append(finding)

    log_agent(state["scan_id"], "OWASPMapper", f"OWASP mapping complete with {len(mapped)} categories")

    return merge_state(
        state,
        {
            "owasp_mapped": mapped,
            "owasp_categories": list(mapped.keys()),
            "analysis_stage": "owasp_mapped",
            "phase": "analysis_completed",
        },
    )
