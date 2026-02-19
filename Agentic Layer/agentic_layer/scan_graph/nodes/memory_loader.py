from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def memory_loader_node(state: ScanState) -> ScanState:
    # Mock historical context loader.
    # In production this node can fetch prior scan runs from DB or vector store.
    log_agent(state["scan_id"], "MemoryLoader", "Loading historical scan context (mock)")
    repo_metadata = dict(state["repo_metadata"])
    repo_metadata["historical_context"] = {
        "previous_findings_count": 0,
        "last_scan_status": "none",
        "source": "mock",
    }

    return merge_state(
        state,
        {
            "phase": "memory_loaded",
            "repo_metadata": repo_metadata,
        },
    )
