from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _normalize_finding(scan_id: str, raw: dict, index: int) -> dict:
    return {
        "id": f"{scan_id}-{raw.get('scanner', 'unknown')}-{index}",
        "scanner": raw.get("scanner", "unknown"),
        "type": raw.get("type", "unknown"),
        "severity": raw.get("severity", "low"),
        "file": raw.get("file", ""),
        "line": raw.get("line", 1),
        "message": raw.get("message", ""),
        "evidence": raw.get("evidence", ""),
        "category_hint": raw.get("category_hint", "general"),
    }


async def signal_aggregator_node(state: ScanState) -> ScanState:
    # Aggregator normalizes heterogeneous scanner outputs into one findings schema.
    log_agent(state["scan_id"], "SignalAggregator", "Aggregating tool outputs into normalized findings")

    normalized: list[dict] = []
    dedupe_keys: set[tuple] = set()

    for tool_output in state["raw_tool_outputs"]:
        for idx, finding in enumerate(tool_output.get("findings", [])):
            normalized_item = _normalize_finding(state["scan_id"], finding, idx)
            dedupe_key = (
                normalized_item["scanner"],
                normalized_item["type"],
                normalized_item["file"],
                normalized_item["line"],
            )
            if dedupe_key in dedupe_keys:
                continue
            dedupe_keys.add(dedupe_key)
            normalized.append(normalized_item)

    next_phase = "signals_aggregated_after_rescan" if state["analysis_phase"] == "rescanned" else "signals_aggregated"
    log_agent(state["scan_id"], "SignalAggregator", f"Aggregation complete with {len(normalized)} normalized findings")
    return merge_state(state, {"findings": normalized, "analysis_phase": next_phase})
