from __future__ import annotations

import subprocess

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def error_handler_node(state: ScanState) -> ScanState:
    # Unified failure path for validation/auth/setup errors.
    # Keeps state shape stable for API responses.
    log_agent(state["scan_id"], "ErrorHandler", f"Entered error handler with {len(state['errors'])} errors")
    errors = list(state["errors"])
    cleanup_status = dict(state.get("cleanup_status", {}))

    if not bool(cleanup_status.get("persistence_completed")):
        errors.append("Persistence not completed before workflow failure")

    if not bool(cleanup_status.get("volume_removed")):
        volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
        if volume_name:
            try:
                completed = subprocess.run(
                    ["docker", "volume", "rm", "-f", volume_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                output = f"{completed.stdout}\n{completed.stderr}".strip()
                if completed.returncode == 0 or "No such volume" in output:
                    cleanup_status["volume_removed"] = True
                    log_agent(state["scan_id"], "ErrorHandler", f"Forced cleanup removed volume {volume_name}")
                else:
                    errors.append(f"Forced cleanup failed for volume {volume_name}: {output[:240]}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Forced cleanup raised exception for volume {volume_name}: {exc}")

    if not errors:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": ["Unknown scan error"],
                "cleanup_status": cleanup_status,
            },
        )

    return merge_state(
        state,
        {
            "phase": "error",
            "errors": errors,
            "cleanup_status": cleanup_status,
        },
    )
