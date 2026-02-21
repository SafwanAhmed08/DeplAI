from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.strategic.layer11 import executive_summary_builder_node
from agentic_layer.scan_graph.nodes.strategic.layer11 import export_formats_preparer_node
from agentic_layer.scan_graph.nodes.strategic.layer11 import security_posture_builder_node
from agentic_layer.scan_graph.state import ScanState


def build_strategic_interface_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("executive_summary_builder", executive_summary_builder_node)
    graph.add_node("security_posture_builder", security_posture_builder_node)
    graph.add_node("export_formats_preparer", export_formats_preparer_node)

    graph.add_edge(START, "executive_summary_builder")
    graph.add_edge("executive_summary_builder", "security_posture_builder")
    graph.add_edge("security_posture_builder", "export_formats_preparer")
    graph.add_edge("export_formats_preparer", END)

    return graph.compile()


strategic_interface_subgraph = build_strategic_interface_subgraph()
