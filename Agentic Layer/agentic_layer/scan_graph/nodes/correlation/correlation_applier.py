from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


CORRELATION_WEIGHTS: dict[str, dict[str, float]] = {
    "A01": {"A05": 0.15},
    "A02": {"A05": 0.1},
    "A03": {"A05": 0.2},
    "A05": {"A01": 0.1, "A03": 0.1},
    "A06": {"A05": 0.15},
}


def _owasp_code(category: str) -> str:
    # Input example: A03:2021-Injection
    return category.split(":", 1)[0].strip()


async def correlation_applier_node(state: ScanState) -> ScanState:
    # Applies deterministic relationship-based score adjustments.
    log_agent(state["scan_id"], "CorrelationApplier", "Adjusting category scores using vulnerability relationships")

    correlated_scores = {category: float(score) for category, score in state["base_scores"].items()}
    code_to_category = {_owasp_code(category): category for category in state["base_scores"]}

    for source_code, related in CORRELATION_WEIGHTS.items():
        source_category = code_to_category.get(source_code)
        if source_category is None:
            continue
        source_score = state["base_scores"].get(source_category, 0.0)

        for target_code, weight in related.items():
            target_category = code_to_category.get(target_code)
            if target_category is None:
                continue
            correlated_scores[target_category] = round(correlated_scores[target_category] + (source_score * weight), 4)

    log_agent(
        state["scan_id"],
        "CorrelationApplier",
        f"Correlation adjustment complete for {len(correlated_scores)} categories",
    )

    return merge_state(
        state,
        {
            "correlated_scores": correlated_scores,
            "correlation_stage": "correlated",
        },
    )
