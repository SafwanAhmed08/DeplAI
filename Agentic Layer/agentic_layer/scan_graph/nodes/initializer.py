from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def state_initializer_node(state: ScanState) -> ScanState:
    # State initializer enriches metadata and marks the scan record initialized.
    log_agent(state["scan_id"], "StateInitializer", "Creating scan record and initializing state")
    repo_metadata = dict(state["repo_metadata"])
    repo_metadata["scan_record"] = {
        "scan_id": state["scan_id"],
        "status": "initialized",
    }

    return merge_state(
        state,
        {
            "phase": "initialized",
            "repo_metadata": repo_metadata,
        },
    )
