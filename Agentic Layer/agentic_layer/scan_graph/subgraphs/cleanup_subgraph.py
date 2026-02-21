from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.cleanup.result_persister import result_persister_node
from agentic_layer.scan_graph.nodes.cleanup.volume_cleanup import volume_cleanup_node
from agentic_layer.scan_graph.state import ScanState


def build_cleanup_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("result_persister", result_persister_node)
    graph.add_node("volume_cleanup", volume_cleanup_node)

    graph.add_edge(START, "result_persister")
    graph.add_edge("result_persister", "volume_cleanup")
    graph.add_edge("volume_cleanup", END)

    return graph.compile()


cleanup_subgraph = build_cleanup_subgraph()
