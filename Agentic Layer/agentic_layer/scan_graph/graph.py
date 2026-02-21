from __future__ import annotations

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.nodes.cleanup.final_event_dispatcher import final_event_dispatcher_node
from agentic_layer.scan_graph.observability import traceable_if_available
from agentic_layer.scan_graph.nodes.error_handler import error_handler_node
from agentic_layer.scan_graph.subgraphs.analysis_subgraph import analysis_subgraph
from agentic_layer.scan_graph.subgraphs.cleanup_subgraph import cleanup_subgraph
from agentic_layer.scan_graph.subgraphs.correlation_subgraph import correlation_subgraph
from agentic_layer.scan_graph.subgraphs.execution_subgraph import execution_subgraph
from agentic_layer.scan_graph.subgraphs.observability_subgraph import observability_subgraph
from agentic_layer.scan_graph.subgraphs.setup_subgraph import setup_subgraph
from agentic_layer.scan_graph.subgraphs.strategic_interface_subgraph import strategic_interface_subgraph
from agentic_layer.scan_graph.subgraphs.validation_init_subgraph import validation_init_subgraph
from agentic_layer.scan_graph.state import append_timeline_event
from agentic_layer.scan_graph.state import PhaseStatus
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def route_if_error(state: ScanState) -> str:
    if state["phase"] == "error" or state["errors"]:
        log_agent(state["scan_id"], "MasterOrchestrator", "Conditional edge selected: error")
        return "error"
    log_agent(state["scan_id"], "MasterOrchestrator", "Conditional edge selected: ok")
    return "ok"


def route_after_setup_phase(state: ScanState) -> str:
    if state["phase"] == "error" or state["errors"]:
        log_agent(state["scan_id"], "MasterOrchestrator", "Setup phase failed; routing to ErrorHandler")
        return "error"

    if state["requires_hitl"]:
        log_agent(state["scan_id"], "MasterOrchestrator", "Setup phase marked requires_hitl=True; skipping analysis pipeline")
        return "hitl"

    log_agent(state["scan_id"], "MasterOrchestrator", "Entering analysis pipeline")
    return "analysis"


def route_after_cleanup_phase(state: ScanState) -> str:
    return "ok"


def route_after_final_event_phase(state: ScanState) -> str:
    cleanup_status = dict(state.get("cleanup_status", {}))
    persistence_completed = bool(cleanup_status.get("persistence_completed"))
    if not persistence_completed:
        log_agent(state["scan_id"], "MasterOrchestrator", "Cleanup persistence incomplete; routing to ErrorHandler")
        return "error"
    return "ok"


def _set_phase_status(state: ScanState, phase_field: str, status: PhaseStatus) -> ScanState:
    next_state = merge_state(state, {phase_field: status.value})
    return append_timeline_event(next_state, phase_field, status.value)


def _mark_phase_failed(state: ScanState, phase_field: str, error_message: str) -> ScanState:
    failed_state = merge_state(
        state,
        {
            phase_field: PhaseStatus.FAILED.value,
            "phase": "error",
            "errors": [*state["errors"], error_message],
        },
    )
    return append_timeline_event(failed_state, phase_field, PhaseStatus.FAILED.value)


async def mark_hitl_required_node(state: ScanState) -> ScanState:
    next_state = _set_phase_status(state, "analysis_phase", PhaseStatus.SKIPPED)
    next_state = _set_phase_status(next_state, "correlation_phase", PhaseStatus.SKIPPED)
    next_state = _set_phase_status(next_state, "execution_phase", PhaseStatus.SKIPPED)
    return merge_state(
        next_state,
        {
            "phase": "hitl_required",
            "analysis_phase": PhaseStatus.SKIPPED.value,
            "correlation_phase": PhaseStatus.SKIPPED.value,
            "execution_phase": PhaseStatus.SKIPPED.value,
            "analysis_stage": "skipped_due_to_size",
            "correlation_stage": "skipped_due_to_hitl",
            "execution_stage": "skipped_due_to_hitl",
        },
    )


@traceable_if_available(name="master.run_analysis_phase", run_type="chain")
async def run_analysis_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to AnalysisSubgraph")
    started_state = _set_phase_status(state, "analysis_phase", PhaseStatus.RUNNING)
    try:
        next_state = await analysis_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        return _mark_phase_failed(started_state, "analysis_phase", f"Analysis phase failed: {exc}")
    completed_state = merge_state(next_state, {"analysis_phase": PhaseStatus.COMPLETED.value})
    return append_timeline_event(completed_state, "analysis_phase", PhaseStatus.COMPLETED.value)


@traceable_if_available(name="master.run_correlation_decision_phase", run_type="chain")
async def run_correlation_decision_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to CorrelationDecisionSubgraph")
    started_state = _set_phase_status(state, "correlation_phase", PhaseStatus.RUNNING)
    try:
        next_state = await correlation_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        return _mark_phase_failed(started_state, "correlation_phase", f"Correlation phase failed: {exc}")
    completed_state = merge_state(next_state, {"correlation_phase": PhaseStatus.COMPLETED.value})
    return append_timeline_event(completed_state, "correlation_phase", PhaseStatus.COMPLETED.value)


@traceable_if_available(name="master.run_execution_phase", run_type="chain")
async def run_execution_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to ExecutionSubgraph")
    started_state = _set_phase_status(state, "execution_phase", PhaseStatus.RUNNING)
    try:
        next_state = await execution_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        return _mark_phase_failed(started_state, "execution_phase", f"Execution phase failed: {exc}")
    completed_state = merge_state(next_state, {"execution_phase": PhaseStatus.COMPLETED.value})
    return append_timeline_event(completed_state, "execution_phase", PhaseStatus.COMPLETED.value)


@traceable_if_available(name="master.run_cleanup_phase", run_type="chain")
async def run_cleanup_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to CleanupSubgraph")
    started_state = append_timeline_event(state, "cleanup_phase", "started")
    try:
        next_state = await cleanup_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        failed_state = merge_state(
            started_state,
            {
                "phase": "error",
                "errors": [*started_state["errors"], f"Cleanup phase failed: {exc}"],
            },
        )
        return append_timeline_event(failed_state, "cleanup_phase", "failed")
    return append_timeline_event(next_state, "cleanup_phase", "completed")


@traceable_if_available(name="master.run_observability_phase", run_type="chain")
async def run_observability_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to ObservabilitySubgraph")
    started_state = append_timeline_event(state, "observability_phase", "started")
    try:
        next_state = await observability_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer10", f"Observability phase failed (non-blocking): {exc}")
        return append_timeline_event(started_state, "observability_phase", "failed")
    return append_timeline_event(next_state, "observability_phase", "completed")


@traceable_if_available(name="master.run_strategic_interface_phase", run_type="chain")
async def run_strategic_interface_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to StrategicInterfaceSubgraph")
    started_state = append_timeline_event(state, "strategic_interface_phase", "started")
    try:
        next_state = await strategic_interface_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer11", f"Strategic interface phase failed (non-blocking): {exc}")
        return append_timeline_event(started_state, "strategic_interface_phase", "failed")
    return append_timeline_event(next_state, "strategic_interface_phase", "completed")


@traceable_if_available(name="master.run_final_event_phase", run_type="chain")
async def run_final_event_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to FinalEventDispatcher")
    started_state = append_timeline_event(state, "final_event_phase", "started")
    next_state = await final_event_dispatcher_node(started_state)
    return append_timeline_event(next_state, "final_event_phase", "completed")


@traceable_if_available(name="master.run_setup_phase", run_type="chain")
async def run_setup_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to SetupSubgraph")
    started_state = _set_phase_status(state, "setup_phase", PhaseStatus.RUNNING)
    try:
        next_state = await setup_subgraph.ainvoke(started_state, config=config)
    except Exception as exc:  # noqa: BLE001
        return _mark_phase_failed(started_state, "setup_phase", f"Setup phase failed: {exc}")

    if next_state["phase"] == "error" or next_state["errors"]:
        failed_state = merge_state(next_state, {"setup_phase": PhaseStatus.FAILED.value})
        return append_timeline_event(failed_state, "setup_phase", PhaseStatus.FAILED.value)

    completed_state = merge_state(next_state, {"setup_phase": PhaseStatus.COMPLETED.value})
    return append_timeline_event(completed_state, "setup_phase", PhaseStatus.COMPLETED.value)


@traceable_if_available(name="master.run_validation_init_phase", run_type="chain")
async def run_validation_init_phase_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    log_agent(state["scan_id"], "MasterOrchestrator", "Delegating to ValidationInitSubgraph")
    started_state = append_timeline_event(state, "validation_init_phase", "started")
    next_state = await validation_init_subgraph.ainvoke(started_state, config=config)
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
    graph.add_node("run_execution_phase", run_execution_phase_node)
    graph.add_node("run_cleanup_phase", run_cleanup_phase_node)
    graph.add_node("run_observability_phase", run_observability_phase_node)
    graph.add_node("run_strategic_interface_phase", run_strategic_interface_phase_node)
    graph.add_node("run_final_event_phase", run_final_event_phase_node)
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
            "error": "error_handler",
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
            "ok": "run_execution_phase",
            "error": "error_handler",
        },
    )

    graph.add_conditional_edges(
        "run_execution_phase",
        route_if_error,
        {
            "ok": "run_cleanup_phase",
            "error": "error_handler",
        },
    )

    graph.add_edge("mark_hitl_required", "run_cleanup_phase")

    graph.add_conditional_edges(
        "run_cleanup_phase",
        route_after_cleanup_phase,
        {
            "ok": "run_observability_phase",
            "error": "error_handler",
        },
    )

    graph.add_edge("run_observability_phase", "run_strategic_interface_phase")
    graph.add_edge("run_strategic_interface_phase", "run_final_event_phase")

    graph.add_conditional_edges(
        "run_final_event_phase",
        route_after_final_event_phase,
        {
            "ok": END,
            "error": "error_handler",
        },
    )

    graph.add_edge("error_handler", END)

    return graph.compile()


master_orchestrator_graph = build_master_orchestrator_graph()


@traceable_if_available(name="master.execute_scan_workflow", run_type="chain")
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
