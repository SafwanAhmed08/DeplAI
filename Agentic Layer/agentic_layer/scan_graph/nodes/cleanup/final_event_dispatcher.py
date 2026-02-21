from __future__ import annotations

from datetime import datetime
from datetime import timezone

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _duration_seconds(state: ScanState) -> float:
    timeline = list(state.get("phase_timeline", []))
    if not timeline:
        return 0.0
    started_at = timeline[0].get("at")
    if not isinstance(started_at, str):
        return 0.0
    try:
        start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    now = datetime.now(timezone.utc)
    delta = now - start_dt
    return max(0.0, round(delta.total_seconds(), 3))


async def final_event_dispatcher_node(state: ScanState) -> ScanState:
    cleanup_status = dict(state.get("cleanup_status", {}))

    if bool(cleanup_status.get("completed")):
        return merge_state(state, {"cleanup_status": cleanup_status, "phase": "completed"})

    total_findings = int(cleanup_status.get("persisted_count", len(state.get("intelligent_findings", []))))
    duration_seconds = _duration_seconds(state)
    status = "completed" if bool(cleanup_status.get("persistence_completed")) else "failed"

    log_agent(
        state["scan_id"],
        "FinalEventDispatcher",
        f"Scan completed: scan_id={state['scan_id']} findings={total_findings} duration_s={duration_seconds} status={status}",
    )

    cleanup_status["completed"] = True

    return merge_state(
        state,
        {
            "cleanup_status": cleanup_status,
            "phase": "completed",
            "repo_metadata": {
                **state["repo_metadata"],
                "final_event": {
                    "scan_id": state["scan_id"],
                    "total_findings": total_findings,
                    "duration_seconds": duration_seconds,
                    "status": status,
                },
            },
        },
    )
