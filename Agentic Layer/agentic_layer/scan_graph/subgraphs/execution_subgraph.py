from __future__ import annotations

from typing import Any
from typing import TypedDict

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.runtime.tool_runtime import ToolRuntime
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state
from agentic_layer.scan_graph.subgraphs.smart_dedup_subgraph import smart_dedup_subgraph


TOOL_CATALOG = {
    "A01:2021-Broken Access Control": ["access_path_scan", "policy_gap_scan"],
    "A02:2021-Cryptographic Failures": ["crypto_key_scan", "config_entropy_check"],
    "A03:2021-Injection": ["ast_deep_scan", "regex_injection", "taint_sim"],
}

TOOL_WEIGHT = {
    "taint_sim": 100,
    "ast_deep_scan": 90,
    "regex_injection": 80,
    "crypto_key_scan": 85,
    "config_entropy_check": 70,
    "access_path_scan": 75,
    "policy_gap_scan": 65,
    "generic_pattern_scan": 50,
}


class CategoryExecutionState(TypedDict):
    scan_id: str
    repo_path: str | None
    category: str
    base_findings: list[dict[str, Any]]
    category_execution_context: dict[str, Any]
    category_status: str
    selected_tools: list[str]
    ordered_tools: list[str]
    tool_outputs: list[dict[str, Any]]
    execution_record: list[dict[str, Any]]
    aggregated_findings: list[dict[str, Any]]
    category_confidence: float


async def execution_coordinator_node(state: ScanState) -> ScanState:
    execution_plan = list(state["execution_plan"])
    selected_categories = list(
        state.get("selected_categories")
        or state.get("filtered_categories")
        or state.get("selected_owasp_categories")
        or []
    )

    if not execution_plan:
        log_agent(state["scan_id"], "ExecutionCoordinator", "Execution plan missing; skipping category execution")
        return merge_state(
            state,
            {
                "execution_stage": "execution_started",
                "layer6_results": [],
            },
        )

    if not selected_categories:
        log_agent(state["scan_id"], "ExecutionCoordinator", "No selected categories found; skipping category execution")
        return merge_state(
            state,
            {
                "execution_stage": "execution_started",
                "layer6_results": [],
            },
        )

    log_agent(
        state["scan_id"],
        "ExecutionCoordinator",
        f"Validated execution inputs: plan={len(execution_plan)} selected={len(selected_categories)}",
    )
    return merge_state(state, {"execution_stage": "execution_started", "layer6_results": []})


def route_after_execution_coordinator(state: ScanState) -> str:
    if not state["execution_plan"]:
        log_agent(state["scan_id"], "ExecutionCoordinator", "Routing directly to ResultMerger (empty plan)")
        return "empty"

    selected_categories = list(
        state.get("selected_categories")
        or state.get("filtered_categories")
        or state.get("selected_owasp_categories")
        or []
    )
    if not selected_categories:
        log_agent(state["scan_id"], "ExecutionCoordinator", "Routing directly to ResultMerger (empty categories)")
        return "empty"

    log_agent(state["scan_id"], "ExecutionCoordinator", "Routing to CategorySubgraphRunner")
    return "run"


async def subgraph_init_node(state: CategoryExecutionState) -> CategoryExecutionState:
    log_agent(state["scan_id"], "SubgraphInit", f"Initializing category context for {state['category']}")
    context = {
        "category": state["category"],
        "repo_path": state["repo_path"],
        "base_finding_count": len(state["base_findings"]),
    }
    return {
        **state,
        "category_execution_context": context,
        "category_status": "running",
    }


async def tool_selector_node(state: CategoryExecutionState) -> CategoryExecutionState:
    selected_tools = TOOL_CATALOG.get(state["category"], ["generic_pattern_scan"])
    log_agent(
        state["scan_id"],
        "ToolSelector",
        f"Selected {len(selected_tools)} tools for {state['category']}",
    )
    return {
        **state,
        "selected_tools": selected_tools,
        "category_execution_context": {
            **state["category_execution_context"],
            "selected_tools": selected_tools,
        },
    }


async def tool_prioritizer_node(state: CategoryExecutionState) -> CategoryExecutionState:
    ordered_tools = sorted(
        state["selected_tools"],
        key=lambda tool: TOOL_WEIGHT.get(tool, 0),
        reverse=True,
    )
    log_agent(
        state["scan_id"],
        "ToolPrioritizer",
        f"Prioritized {len(ordered_tools)} tools for {state['category']}",
    )
    return {
        **state,
        "ordered_tools": ordered_tools,
        "category_execution_context": {
            **state["category_execution_context"],
            "ordered_tools": ordered_tools,
        },
    }


async def docker_executor_node(state: CategoryExecutionState) -> CategoryExecutionState:
    runtime = ToolRuntime(scan_id=state["scan_id"])
    outputs: list[dict[str, Any]] = []
    for tool_name in state["ordered_tools"]:
        repo_path = state["repo_path"] or ""
        try:
            result = runtime.run_tool(tool_name=tool_name, repo_path=repo_path)
        except Exception as exc:  # noqa: BLE001
            log_agent(
                state["scan_id"],
                "DockerExecutor",
                f"Tool execution failed for {tool_name}: {exc}",
            )
            result = {
                "tool_name": tool_name,
                "exit_code": 1,
                "execution_time_ms": 0,
                "stdout": "",
                "stderr": str(exc),
                "status": "failed",
                "parsed_findings": [],
                "summary": {},
            }

        parsed_findings = list(result["parsed_findings"])
        confidence_values = [float(item.get("confidence", 0.5)) for item in parsed_findings]
        average_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0

        outputs.append(
            {
                "tool_name": result["tool_name"],
                "exit_code": result["exit_code"],
                "execution_time_ms": result["execution_time_ms"],
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "status": result.get("status", "failed"),
                "parsed_findings": parsed_findings,
                "findings": parsed_findings,
                "confidence_score": average_confidence,
                "summary": result.get("summary", {}),
            }
        )

    log_agent(
        state["scan_id"],
        "DockerExecutor",
        f"Container execution complete for {state['category']} with {len(outputs)} tool outputs",
    )
    return {**state, "tool_outputs": outputs}


async def execution_recorder_node(state: CategoryExecutionState) -> CategoryExecutionState:
    execution_record = [
        {
            "tool_name": output["tool_name"],
            "execution_time": output["execution_time_ms"],
            "status": output.get("status", "failed"),
            "confidence": output["confidence_score"],
            "finding_count": len(output["findings"]),
        }
        for output in state["tool_outputs"]
    ]
    log_agent(
        state["scan_id"],
        "ExecutionRecorder",
        f"Recorded {len(execution_record)} tool runs for {state['category']}",
    )
    return {**state, "execution_record": execution_record}


async def result_aggregator_node(state: CategoryExecutionState) -> CategoryExecutionState:
    aggregated: list[dict[str, Any]] = []
    for output in state["tool_outputs"]:
        for finding in output["findings"]:
            aggregated.append(
                {
                    "category": finding["category"],
                    "title": finding["title"],
                    "severity": finding["severity"],
                    "evidence": finding["evidence"],
                    "tool_provenance": finding["tool_provenance"],
                    "confidence": finding["confidence"],
                    "reasoning": finding["reasoning"],
                    "origin_parser": finding.get("origin_parser", "strict_json"),
                }
            )

    log_agent(
        state["scan_id"],
        "ResultAggregator",
        f"Aggregated {len(aggregated)} findings for {state['category']}",
    )
    return {**state, "aggregated_findings": aggregated}


async def conditional_evaluator_node(state: CategoryExecutionState) -> CategoryExecutionState:
    confidences = [float(item["confidence"]) for item in state["aggregated_findings"]]
    average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    category_status = "completed" if average_confidence >= 0.6 else "low_confidence"

    log_agent(
        state["scan_id"],
        "ConditionalEvaluator",
        f"Category {state['category']} status={category_status} confidence={average_confidence}",
    )
    return {
        **state,
        "category_status": category_status,
        "category_confidence": average_confidence,
    }


def build_category_subgraph():
    graph = StateGraph(CategoryExecutionState)

    graph.add_node("subgraph_init", subgraph_init_node)
    graph.add_node("tool_selector", tool_selector_node)
    graph.add_node("tool_prioritizer", tool_prioritizer_node)
    graph.add_node("docker_executor", docker_executor_node)
    graph.add_node("execution_recorder", execution_recorder_node)
    graph.add_node("result_aggregator", result_aggregator_node)
    graph.add_node("conditional_evaluator", conditional_evaluator_node)

    graph.add_edge(START, "subgraph_init")
    graph.add_edge("subgraph_init", "tool_selector")
    graph.add_edge("tool_selector", "tool_prioritizer")
    graph.add_edge("tool_prioritizer", "docker_executor")
    graph.add_edge("docker_executor", "execution_recorder")
    graph.add_edge("execution_recorder", "result_aggregator")
    graph.add_edge("result_aggregator", "conditional_evaluator")
    graph.add_edge("conditional_evaluator", END)

    return graph.compile()


category_subgraph = build_category_subgraph()


async def category_subgraph_runner_node(state: ScanState) -> ScanState:
    plan = sorted(state["execution_plan"], key=lambda item: int(item.get("order", 0)))
    layer6_results: list[dict[str, Any]] = []

    for plan_item in plan:
        category = str(plan_item.get("category", "")).strip()
        if not category:
            continue

        initial_category_state: CategoryExecutionState = {
            "scan_id": state["scan_id"],
            "repo_path": state["repo_path"],
            "category": category,
            "base_findings": list(state["owasp_mapped"].get(category, [])),
            "category_execution_context": {},
            "category_status": "pending",
            "selected_tools": [],
            "ordered_tools": [],
            "tool_outputs": [],
            "execution_record": [],
            "aggregated_findings": [],
            "category_confidence": 0.0,
        }

        final_category_state = await category_subgraph.ainvoke(initial_category_state)
        layer6_results.append(
            {
                "category": category,
                "order": int(plan_item.get("order", 0)),
                "score": float(plan_item.get("score", 0.0)),
                "category_status": final_category_state["category_status"],
                "category_confidence": final_category_state["category_confidence"],
                "execution_record": final_category_state["execution_record"],
                "aggregated_findings": final_category_state["aggregated_findings"],
            }
        )
        log_agent(
            state["scan_id"],
            "CategorySubgraphRunner",
            f"Completed category subgraph for {category} with {len(final_category_state['aggregated_findings'])} findings",
        )

    return merge_state(
        state,
        {
            "layer6_results": layer6_results,
            "execution_stage": "category_execution_completed",
        },
    )


async def result_merger_node(state: ScanState) -> ScanState:
    layer6_findings: list[dict[str, Any]] = []
    for result in state["layer6_results"]:
        layer6_findings.extend(result.get("aggregated_findings", []))

    final_findings = [*state["normalized_findings"], *layer6_findings]
    log_agent(
        state["scan_id"],
        "ResultMerger",
        f"Merged findings: normalized={len(state['normalized_findings'])}, layer6={len(layer6_findings)}, total={len(final_findings)}",
    )
    return merge_state(
        state,
        {
            "final_findings": final_findings,
            "execution_stage": "execution_merged",
        },
    )


async def run_smart_dedup_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "ExecutionSubgraph", "Delegating to SmartDedupSubgraph")
    next_state = await smart_dedup_subgraph.ainvoke(state)
    return merge_state(
        next_state,
        {
            "execution_stage": "execution_completed",
            "phase": "execution_completed",
        },
    )


def build_execution_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("execution_coordinator", execution_coordinator_node)
    graph.add_node("category_subgraph_runner", category_subgraph_runner_node)
    graph.add_node("result_merger", result_merger_node)
    graph.add_node("run_smart_dedup", run_smart_dedup_node)

    graph.add_edge(START, "execution_coordinator")

    graph.add_conditional_edges(
        "execution_coordinator",
        route_after_execution_coordinator,
        {
            "run": "category_subgraph_runner",
            "empty": "result_merger",
        },
    )

    graph.add_edge("category_subgraph_runner", "result_merger")
    graph.add_edge("result_merger", "run_smart_dedup")
    graph.add_edge("run_smart_dedup", END)

    return graph.compile()


execution_subgraph = build_execution_subgraph()
