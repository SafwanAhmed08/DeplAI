from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.nodes.error_handler import error_handler_node
from agentic_layer.scan_graph.subgraphs.analysis_subgraph import analysis_subgraph
from agentic_layer.scan_graph.subgraphs.correlation_subgraph import correlation_subgraph
from agentic_layer.scan_graph.subgraphs.setup_subgraph import setup_subgraph
from agentic_layer.scan_graph.subgraphs.validation_init_subgraph import validation_init_subgraph
from agentic_layer.scan_graph.state import append_timeline_event
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def route_if_error(state: ScanState) -> str:
    if state["phase"] == "error" or state["errors"]:
        log_agent(state["scan_id"], "MasterOrchestrator", "Conditional edge selected: error")
        return "error"
    log_agent(state["scan_id"], "MasterOrchestrator", "Conditional edge selected: ok")
    return "ok"


def route_after_setup_phase(state: ScanState) -> str:
    if state["requires_hitl"]:
        log_agent(state["scan_id"], "MasterOrchestrator", "Setup phase marked requires_hitl=True; skipping analysis pipeline")
        return "hitl"

    log_agent(state["scan_id"], "MasterOrchestrator", "Entering analysis pipeline")
    return "analysis"


async def mark_hitl_required_node(state: ScanState) -> ScanState:
    next_state = merge_state(
        state,
        {
            "phase": "hitl_required",
            "analysis_phase": "skipped_due_to_size",
            "correlation_phase": "skipped_due_to_hitl",
        },
    )
    return append_timeline_event(next_state, "analysis_phase", "skipped_due_to_hitl")


async def run_analysis_phase_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to AnalysisSubgraph")
    started_state = append_timeline_event(state, "analysis_phase", "started")
    next_state = await analysis_subgraph.ainvoke(started_state)
    return append_timeline_event(next_state, "analysis_phase", "completed")


async def run_correlation_decision_phase_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to CorrelationDecisionSubgraph")
    started_state = append_timeline_event(state, "correlation_phase", "started")
    next_state = await correlation_subgraph.ainvoke(started_state)
    return append_timeline_event(next_state, "correlation_phase", "completed")


async def run_setup_phase_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to SetupSubgraph")
    started_state = append_timeline_event(state, "setup_phase", "started")
    next_state = await setup_subgraph.ainvoke(started_state)
    return append_timeline_event(next_state, "setup_phase", "completed")


async def run_validation_init_phase_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to ValidationInitSubgraph")
    started_state = append_timeline_event(state, "validation_init_phase", "started")
    next_state = await validation_init_subgraph.ainvoke(started_state)
    next_state = append_timeline_event(next_state, "validation_init_phase", "completed")
    if next_state["errors"]:
        return merge_state(next_state, {"phase": "error"})
    return next_state


def build_master_orchestrator_graph():
    # StateGraph defines deterministic workflow over typed shared state.
    graph = StateGraph(ScanState)

    graph.add_node("run_validation_init_phase", run_validation_init_phase_node)
    graph.add_node("run_setup_phase", run_setup_phase_node)
    graph.add_node("run_analysis_phase", run_analysis_phase_node)
    graph.add_node("run_correlation_decision_phase", run_correlation_decision_phase_node)
    graph.add_node("mark_hitl_required", mark_hitl_required_node)
    graph.add_node("error_handler", error_handler_node)

    graph.add_edge(START, "run_validation_init_phase")

    graph.add_conditional_edges(
        "run_validation_init_phase",
        route_if_error,
        {
            "ok": "run_setup_phase",
            "error": "error_handler",
        },
    )

    graph.add_conditional_edges(
        "run_setup_phase",
        route_after_setup_phase,
        {
            "analysis": "run_analysis_phase",
            "hitl": "mark_hitl_required",
        },
    )

    graph.add_conditional_edges(
        "run_analysis_phase",
        route_if_error,
        {
            "ok": "run_correlation_decision_phase",
            "error": "error_handler",
        },
    )

    graph.add_conditional_edges(
        "run_correlation_decision_phase",
        route_if_error,
        {
            "ok": END,
            "error": "error_handler",
        },
    )

    graph.add_edge("mark_hitl_required", END)

    graph.add_edge("error_handler", END)

    return graph.compile()


master_orchestrator_graph = build_master_orchestrator_graph()


async def execute_scan_workflow(state: ScanState) -> ScanState:
    # Entry-point used by FastAPI route.
    started_state = append_timeline_event(state, "master_orchestrator", "started")
    log_agent(started_state["scan_id"], "MasterOrchestrator", "Workflow execution started")
    final_state = await master_orchestrator_graph.ainvoke(started_state)
    final_state = append_timeline_event(final_state, "master_orchestrator", "completed")
    log_agent(
        final_state["scan_id"],
        "MasterOrchestrator",
        f"Workflow execution finished at phase={final_state['phase']} with errors={len(final_state['errors'])}",
    )
    return final_state
