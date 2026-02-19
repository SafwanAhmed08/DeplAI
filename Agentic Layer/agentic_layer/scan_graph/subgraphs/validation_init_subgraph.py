from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.nodes.github_auth import github_auth_node
from agentic_layer.scan_graph.nodes.initializer import state_initializer_node
from agentic_layer.scan_graph.nodes.validator import request_validator_node
from agentic_layer.scan_graph.nodes.validator import route_after_validation
from agentic_layer.scan_graph.state import ScanState


def route_if_error(state: ScanState) -> str:
    if state["phase"] == "error" or state["errors"]:
        log_agent(state["scan_id"], "ValidationInitSubgraph", "Conditional edge selected: error")
        return "error"
    log_agent(state["scan_id"], "ValidationInitSubgraph", "Conditional edge selected: ok")
    return "ok"


def build_validation_init_subgraph():
    # Validation+Initialization subgraph encapsulates Layer 2 workflow.
    graph = StateGraph(ScanState)

    graph.add_node("request_validator", request_validator_node)
    graph.add_node("github_auth", github_auth_node)
    graph.add_node("state_initializer", state_initializer_node)

    graph.add_edge(START, "request_validator")

    graph.add_conditional_edges(
        "request_validator",
        route_after_validation,
        {
            "ok": "github_auth",
            "error": END,
        },
    )

    graph.add_conditional_edges(
        "github_auth",
        route_if_error,
        {
            "ok": "state_initializer",
            "error": END,
        },
    )

    graph.add_conditional_edges(
        "state_initializer",
        route_if_error,
        {
            "ok": END,
            "error": END,
        },
    )

    return graph.compile()


validation_init_subgraph = build_validation_init_subgraph()
