from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def result_merger_node(state: ScanState) -> ScanState:
    log_agent(state["scan_id"], "ResultMerger", "Merging execution results into final findings")

    enriched: list[dict] = []
    for result in state["layer6_results"]:
        enriched.extend(result.get("enriched_findings", []))

    final_findings = [*state["findings"], *enriched]

    log_agent(
        state["scan_id"],
        "ResultMerger",
        f"Layer 6 merge complete: base={len(state['findings'])}, enriched={len(enriched)}, total={len(final_findings)}",
    )

    return merge_state(
        state,
        {
            "final_findings": final_findings,
            "execution_stage": "merged",
            "phase": "execution_completed",
        },
    )
