from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
    "info": 0.1,
}


def _severity_weight(severity: str) -> float:
    return SEVERITY_WEIGHTS.get((severity or "").lower(), 0.25)


async def base_scorer_node(state: ScanState) -> ScanState:
    # Computes initial per-category OWASP scores from mapped findings.
    log_agent(state["scan_id"], "BaseScorer", "Calculating initial OWASP category scores")

    base_scores: dict[str, float] = {}
    for category, findings in state["owasp_mapped"].items():
        score = 0.0
        for finding in findings:
            score += _severity_weight(str(finding.get("severity", "low")))
        base_scores[category] = round(score, 4)

    log_agent(
        state["scan_id"],
        "BaseScorer",
        f"Base scoring complete with {len(base_scores)} categories",
    )

    return merge_state(
        state,
        {
            "phase": "correlation_decision",
            "base_scores": base_scores,
            "correlation_phase": "base_scored",
        },
    )
