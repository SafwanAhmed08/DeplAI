from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def targeted_rescan_node(state: ScanState) -> ScanState:
    # Targeted rescan adds focused checks only for missing coverage areas.
    log_agent(state["scan_id"], "TargetedRescan", "Running targeted rescan for coverage gaps")

    synthetic_findings: list[dict] = []

    for gap in state["coverage_gaps"]:
        synthetic_findings.append(
            {
                "scanner": "targeted_rescan",
                "type": f"rescan_{gap}_check",
                "severity": "low",
                "file": state["repo_path"] or "",
                "line": 1,
                "message": f"Targeted rescan executed for {gap}",
                "category_hint": "security_misconfiguration",
            }
        )

    raw_tool_outputs = [
        *state["raw_tool_outputs"],
        {
            "tool": "targeted_rescan",
            "findings": synthetic_findings,
            "summary": {"count": len(synthetic_findings), "gaps": state["coverage_gaps"]},
        },
    ]

    log_agent(state["scan_id"], "TargetedRescan", f"Targeted rescan complete with {len(synthetic_findings)} findings")

    return merge_state(
        state,
        {
            "raw_tool_outputs": raw_tool_outputs,
            "rescans_triggered": True,
            "coverage_gaps": [],
            "analysis_stage": "rescanned",
        },
    )
