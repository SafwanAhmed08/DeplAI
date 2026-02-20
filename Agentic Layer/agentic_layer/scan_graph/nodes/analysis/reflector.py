from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def reflector_node(state: ScanState) -> ScanState:
    # Reflector estimates coverage quality and decides if targeted rescan is needed.
    log_agent(state["scan_id"], "Reflector", "Evaluating coverage gaps")

    scanners_seen = {output.get("tool", "") for output in state["raw_tool_outputs"]}
    gaps: list[str] = []

    required_scanners = {
        "ast_scanner": "ast",
        "regex_scanner": "regex",
        "dependency_scanner": "dependency",
        "config_scanner": "config",
    }

    for scanner_tool, gap_name in required_scanners.items():
        if scanner_tool not in scanners_seen:
            gaps.append(gap_name)

    # Safe loop guard: once a targeted rescan has already run, we stop asking for another pass.
    if state["rescans_triggered"]:
        gaps = []

    log_agent(
        state["scan_id"],
        "Reflector",
        f"Coverage reflection complete: gaps={gaps if gaps else 'none'}",
    )

    return merge_state(
        state,
        {
            "coverage_gaps": gaps,
            "analysis_stage": "reflected",
        },
    )


def route_after_reflector(state: ScanState) -> str:
    if state["coverage_gaps"] and not state["rescans_triggered"]:
        log_agent(state["scan_id"], "Reflector", "Routing to targeted rescan")
        return "rescan"

    log_agent(state["scan_id"], "Reflector", "Routing directly to OWASP mapper")
    return "map"
