from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.nodes.observability.layer10 import execution_intelligence_summary_node
from agentic_layer.scan_graph.nodes.observability.layer10 import structured_audit_record_node
from agentic_layer.scan_graph.nodes.observability.layer10 import structured_scan_telemetry_node
from agentic_layer.scan_graph.state import ScanState


def build_observability_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("structured_scan_telemetry", structured_scan_telemetry_node)
    graph.add_node("execution_intelligence_summary", execution_intelligence_summary_node)
    graph.add_node("structured_audit_record", structured_audit_record_node)

    graph.add_edge(START, "structured_scan_telemetry")
    graph.add_edge("structured_scan_telemetry", "execution_intelligence_summary")
    graph.add_edge("execution_intelligence_summary", "structured_audit_record")
    graph.add_edge("structured_audit_record", END)

    return graph.compile()


observability_subgraph = build_observability_subgraph()
