from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def execution_planner_node(state: ScanState) -> ScanState:
    # Produces deterministic execution order for future OWASP subagent spawning.
    log_agent(state["scan_id"], "ExecutionPlanner", "Building execution plan for OWASP category subagents")

    ranked = sorted(
        state["filtered_categories"],
        key=lambda category: state["correlated_scores"].get(category, 0.0),
        reverse=True,
    )

    execution_plan: list[dict[str, object]] = []
    for order, category in enumerate(ranked, start=1):
        execution_plan.append(
            {
                "order": order,
                "category": category,
                "score": state["correlated_scores"].get(category, 0.0),
            }
        )

    log_agent(
        state["scan_id"],
        "ExecutionPlanner",
        f"Execution planning complete with {len(execution_plan)} planned category subagents",
    )

    return merge_state(
        state,
        {
            "execution_plan": execution_plan,
            "correlation_stage": "planned",
            "phase": "correlation_decision_completed",
        },
    )
