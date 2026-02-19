from __future__ import annotations

from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def volume_creator_node(state: ScanState) -> ScanState:
    # Volume creator maps scan folders for code and output artifacts.
    # Here we model Docker-like volume targets as local directories.
    log_agent(state["scan_id"], "VolumeCreator", "Creating code and artifact volumes")
    scan_root = Path("/tmp") / "deplai_scans" / state["scan_id"]
    code_volume = scan_root / "code"
    output_volume = scan_root / "artifacts"

    code_volume.mkdir(parents=True, exist_ok=True)
    output_volume.mkdir(parents=True, exist_ok=True)

    volumes = {
        "code": str(code_volume),
        "artifacts": str(output_volume),
    }

    log_agent(state["scan_id"], "VolumeCreator", f"Volumes ready at {scan_root}")

    return merge_state(
        state,
        {
            "phase": "volumes_created",
            "docker_volumes": volumes,
            "repo_path": str(code_volume),
        },
    )
