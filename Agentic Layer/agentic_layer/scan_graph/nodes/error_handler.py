from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def error_handler_node(state: ScanState) -> ScanState:
    # Unified failure path for validation/auth/setup errors.
    # Keeps state shape stable for API responses.
    log_agent(state["scan_id"], "ErrorHandler", f"Entered error handler with {len(state['errors'])} errors")
    if not state["errors"]:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": ["Unknown scan error"],
            },
        )

    return merge_state(
        state,
        {
            "phase": "error",
        },
    )
