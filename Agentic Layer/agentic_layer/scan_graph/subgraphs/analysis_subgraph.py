from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.nodes.analysis.ast_scanner import ast_scanner_node
from agentic_layer.scan_graph.nodes.analysis.config_scanner import config_scanner_node
from agentic_layer.scan_graph.nodes.analysis.dependency_scanner import dependency_scanner_node
from agentic_layer.scan_graph.nodes.analysis.owasp_mapper import owasp_mapper_node
from agentic_layer.scan_graph.nodes.analysis.planner import analysis_planner_node
from agentic_layer.scan_graph.nodes.analysis.reflector import reflector_node
from agentic_layer.scan_graph.nodes.analysis.reflector import route_after_reflector
from agentic_layer.scan_graph.nodes.analysis.regex_scanner import regex_scanner_node
from agentic_layer.scan_graph.nodes.analysis.signal_aggregator import signal_aggregator_node
from agentic_layer.scan_graph.nodes.analysis.targeted_rescan import targeted_rescan_node
from agentic_layer.scan_graph.state import ScanState


def route_after_signal_aggregator(state: ScanState) -> str:
    # First aggregation pass goes to reflector.
    # Post-rescan aggregation goes straight to mapper.
    if state["analysis_stage"] == "signals_aggregated_after_rescan":
        log_agent(state["scan_id"], "AnalysisSubgraph", "Post-rescan aggregation complete; routing to OWASP mapper")
        return "map"

    log_agent(state["scan_id"], "AnalysisSubgraph", "Aggregation complete; routing to reflector")
    return "reflect"


def build_analysis_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("analysis_planner", analysis_planner_node)
    graph.add_node("ast_scanner", ast_scanner_node)
    graph.add_node("regex_scanner", regex_scanner_node)
    graph.add_node("dependency_scanner", dependency_scanner_node)
    graph.add_node("config_scanner", config_scanner_node)
    graph.add_node("signal_aggregator", signal_aggregator_node)
    graph.add_node("reflector", reflector_node)
    graph.add_node("targeted_rescan", targeted_rescan_node)
    graph.add_node("owasp_mapper", owasp_mapper_node)

    graph.add_edge(START, "analysis_planner")
    graph.add_edge("analysis_planner", "ast_scanner")
    graph.add_edge("ast_scanner", "regex_scanner")
    graph.add_edge("regex_scanner", "dependency_scanner")
    graph.add_edge("dependency_scanner", "config_scanner")
    graph.add_edge("config_scanner", "signal_aggregator")

    graph.add_conditional_edges(
        "signal_aggregator",
        route_after_signal_aggregator,
        {
            "reflect": "reflector",
            "map": "owasp_mapper",
        },
    )

    graph.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {
            "rescan": "targeted_rescan",
            "map": "owasp_mapper",
        },
    )

    # Safe bounded loop: reflector can request one targeted rescan, then aggregator routes to mapper.
    graph.add_edge("targeted_rescan", "signal_aggregator")
    graph.add_edge("owasp_mapper", END)

    return graph.compile()


analysis_subgraph = build_analysis_subgraph()
