from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def spawn_decider_node(state: ScanState) -> ScanState:
    # Chooses which OWASP categories are eligible for Layer 6 subagent spawning.
    log_agent(state["scan_id"], "SpawnDecider", "Determining OWASP categories eligible for subagent spawning")

    ranked = sorted(state["correlated_scores"].items(), key=lambda item: item[1], reverse=True)
    selected = [category for category, score in ranked if score > 0.0]

    log_agent(
        state["scan_id"],
        "SpawnDecider",
        f"Spawn decision complete: selected={len(selected)} categories",
    )

    return merge_state(
        state,
        {
            "selected_owasp_categories": selected,
            "correlation_stage": "spawn_decided",
        },
    )


def route_after_spawn_decider(state: ScanState) -> str:
    if state["selected_owasp_categories"]:
        log_agent(state["scan_id"], "SpawnDecider", "Selected categories present; routing to Tech Stack Filter")
        return "selected"

    log_agent(state["scan_id"], "SpawnDecider", "No categories selected; continuing to Tech Stack Filter")
    return "none"
