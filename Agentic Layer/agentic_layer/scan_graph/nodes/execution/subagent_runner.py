from __future__ import annotations

from agentic_layer.scan_graph.layer6_subagents.generic_category_runner import run_generic_category
from agentic_layer.scan_graph.layer6_subagents.owasp_a1 import run_owasp_a1
from agentic_layer.scan_graph.layer6_subagents.owasp_a2 import run_owasp_a2
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _select_runner(category: str):
    if category == "A01:2021-Broken Access Control":
        return lambda state: run_owasp_a1(state)
    if category == "A02:2021-Cryptographic Failures":
        return lambda state: run_owasp_a2(state)
    return lambda state: run_generic_category(state, category)


async def subagent_runner_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "SubagentRunner", "Executing OWASP category subagents sequentially")

    layer6_results: list[dict] = []

    sorted_plan = sorted(state["execution_plan"], key=lambda item: int(item.get("order", 0)))

    for item in sorted_plan:
        category = str(item.get("category", ""))
        order = int(item.get("order", 0))
        if not category:
            continue

        runner = _select_runner(category)
        enriched_findings = runner(state)

        layer6_results.append(
            {
                "category": category,
                "order": order,
                "score": item.get("score", 0.0),
                "enriched_findings": enriched_findings,
                "count": len(enriched_findings),
            }
        )

        log_agent(
            state["scan_id"],
            "SubagentRunner",
            f"Completed subagent for {category} with {len(enriched_findings)} enriched findings",
        )

    return merge_state(
        state,
        {
            "phase": "execution_phase",
            "execution_stage": "subagents_completed",
            "layer6_results": layer6_results,
        },
    )
