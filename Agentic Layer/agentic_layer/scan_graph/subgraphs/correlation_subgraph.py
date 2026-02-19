from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.correlation.base_scorer import base_scorer_node
from agentic_layer.scan_graph.nodes.correlation.correlation_applier import correlation_applier_node
from agentic_layer.scan_graph.nodes.correlation.execution_planner import execution_planner_node
from agentic_layer.scan_graph.nodes.correlation.spawn_decider import route_after_spawn_decider
from agentic_layer.scan_graph.nodes.correlation.spawn_decider import spawn_decider_node
from agentic_layer.scan_graph.nodes.correlation.tech_stack_filter import tech_stack_filter_node
from agentic_layer.scan_graph.state import ScanState


def build_correlation_subgraph():
    # Layer 5 Correlation & Decision workflow.
    graph = StateGraph(ScanState)

    graph.add_node("base_scorer", base_scorer_node)
    graph.add_node("correlation_applier", correlation_applier_node)
    graph.add_node("spawn_decider", spawn_decider_node)
    graph.add_node("tech_stack_filter", tech_stack_filter_node)
    graph.add_node("execution_planner", execution_planner_node)

    graph.add_edge(START, "base_scorer")
    graph.add_edge("base_scorer", "correlation_applier")
    graph.add_edge("correlation_applier", "spawn_decider")

    graph.add_conditional_edges(
        "spawn_decider",
        route_after_spawn_decider,
        {
            "selected": "tech_stack_filter",
            "none": "tech_stack_filter",
        },
    )

    graph.add_edge("tech_stack_filter", "execution_planner")
    graph.add_edge("execution_planner", END)

    return graph.compile()


correlation_subgraph = build_correlation_subgraph()
