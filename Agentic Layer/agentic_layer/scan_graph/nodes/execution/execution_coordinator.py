from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def execution_coordinator_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "ExecutionCoordinator", "Validating execution plan and selected categories")

    execution_plan = list(state["execution_plan"])
    valid_categories = set(state["filtered_categories"])

    if not execution_plan:
        log_agent(state["scan_id"], "ExecutionCoordinator", "No execution plan entries found; proceeding with empty run")
        return merge_state(
            state,
            {
                "phase": "execution_phase",
                "execution_stage": "coordinated_empty",
                "layer6_results": [],
            },
        )

    validated_plan = [
        item
        for item in execution_plan
        if isinstance(item, dict) and item.get("category") in valid_categories
    ]

    log_agent(
        state["scan_id"],
        "ExecutionCoordinator",
        f"Execution plan validated: {len(validated_plan)} categories queued",
    )

    return merge_state(
        state,
        {
            "phase": "execution_phase",
            "execution_stage": "coordinated",
            "execution_plan": validated_plan,
        },
    )


def route_after_execution_coordinator(state: ScanState) -> str:
    if state["execution_plan"]:
        log_agent(state["scan_id"], "ExecutionCoordinator", "Routing to SubagentRunner")
        return "run"

    log_agent(state["scan_id"], "ExecutionCoordinator", "Routing to ResultMerger (no categories)")
    return "empty"
