from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


SIZE_THRESHOLD_BYTES = 20 * 1024 * 1024


async def size_checker_node(state: ScanState) -> ScanState:
    # Sets HITL flag when repository exceeds configured threshold.
    log_agent(state["scan_id"], "SizeChecker", "Evaluating repository size threshold")
    repo_metadata = dict(state["repo_metadata"])
    stats = repo_metadata.get("stats", {})
    total_size_bytes = int(stats.get("total_size_bytes", 0))

    requires_hitl = total_size_bytes > SIZE_THRESHOLD_BYTES

    repo_metadata["size_check"] = {
        "threshold_bytes": SIZE_THRESHOLD_BYTES,
        "total_size_bytes": total_size_bytes,
        "requires_hitl": requires_hitl,
    }
    log_agent(
        state["scan_id"],
        "SizeChecker",
        f"Size check complete: total_bytes={total_size_bytes}, requires_hitl={requires_hitl}",
    )

    return merge_state(
        state,
        {
            "phase": "size_checked",
            "requires_hitl": requires_hitl,
            "repo_metadata": repo_metadata,
        },
    )
