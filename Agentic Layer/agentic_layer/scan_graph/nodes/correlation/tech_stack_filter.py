from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _determine_stack_markers(state: ScanState) -> set[str]:
    stats = state["repo_metadata"].get("stats", {})
    language_breakdown = stats.get("language_breakdown", {})
    markers: set[str] = {language for language, count in language_breakdown.items() if isinstance(count, int) and count > 0}

    analysis_plan = state["repo_metadata"].get("analysis_plan", {})
    if analysis_plan.get("run_dependency_scanner"):
        markers.add("dependency_manifests")
    if analysis_plan.get("run_config_scanner"):
        markers.add("config_files")

    return markers


async def tech_stack_filter_node(state: ScanState) -> ScanState:
    # Applies architecture/stack-aware filtering to selected OWASP categories.
    log_agent(state["scan_id"], "TechStackFilter", "Applying architecture-based filtering to selected categories")

    selected = list(state["selected_owasp_categories"])
    stack_markers = _determine_stack_markers(state)

    filtered: list[str] = []
    for category in selected:
        # A06 has highest value when dependency evidence exists.
        if category.startswith("A06") and "dependency_manifests" not in stack_markers:
            continue
        filtered.append(category)

    log_agent(
        state["scan_id"],
        "TechStackFilter",
        f"Tech stack filtering complete: kept={len(filtered)} of selected={len(selected)}",
    )

    return merge_state(
        state,
        {
            "filtered_categories": filtered,
            "correlation_stage": "filtered",
        },
    )
