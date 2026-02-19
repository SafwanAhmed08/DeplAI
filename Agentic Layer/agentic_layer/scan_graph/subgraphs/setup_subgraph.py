from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.cloner import cloner_node
from agentic_layer.scan_graph.nodes.memory_loader import memory_loader_node
from agentic_layer.scan_graph.nodes.size_checker import size_checker_node
from agentic_layer.scan_graph.nodes.stats import codebase_stats_node
from agentic_layer.scan_graph.nodes.volume_creator import volume_creator_node
from agentic_layer.scan_graph.state import ScanState


def build_setup_subgraph():
    # Setup subgraph encapsulates Layer 3 (Setup & Acquisition) as one reusable phase.
    graph = StateGraph(ScanState)

    graph.add_node("volume_creator", volume_creator_node)
    graph.add_node("cloner", cloner_node)
    graph.add_node("codebase_stats", codebase_stats_node)
    graph.add_node("memory_loader", memory_loader_node)
    graph.add_node("size_checker", size_checker_node)

    graph.add_edge(START, "volume_creator")
    graph.add_edge("volume_creator", "cloner")
    graph.add_edge("cloner", "codebase_stats")
    graph.add_edge("codebase_stats", "memory_loader")
    graph.add_edge("memory_loader", "size_checker")
    graph.add_edge("size_checker", END)

    return graph.compile()


setup_subgraph = build_setup_subgraph()
