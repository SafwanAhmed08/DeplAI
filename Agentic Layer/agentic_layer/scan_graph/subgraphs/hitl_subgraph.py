from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.hitl.decision_gate import hitl_apply_decision_node
from agentic_layer.scan_graph.nodes.hitl.decision_gate import hitl_prompt_node
from agentic_layer.scan_graph.nodes.hitl.decision_gate import hitl_wait_for_decision_node
from agentic_layer.scan_graph.state import ScanState


def build_hitl_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("hitl_prompt", hitl_prompt_node)
    graph.add_node("hitl_wait_for_decision", hitl_wait_for_decision_node)
    graph.add_node("hitl_apply_decision", hitl_apply_decision_node)

    graph.add_edge(START, "hitl_prompt")
    graph.add_edge("hitl_prompt", "hitl_wait_for_decision")
    graph.add_edge("hitl_wait_for_decision", "hitl_apply_decision")
    graph.add_edge("hitl_apply_decision", END)

    return graph.compile()


hitl_subgraph = build_hitl_subgraph()
