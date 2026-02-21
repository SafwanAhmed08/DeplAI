from __future__ import annotations

import re
import subprocess

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _build_code_volume_name(scan_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_.-]", "_", scan_id).lower()
    if not normalized:
        normalized = "unknown"
    return f"deplai_code_{normalized}"


async def volume_creator_node(state: ScanState) -> ScanState:
    # Layer 3 volume creator provisions persistent Docker named volumes.
    log_agent(state["scan_id"], "VolumeCreator", "Creating persistent Docker code volume")
    code_volume_name = _build_code_volume_name(state["scan_id"])

    try:
        created_name = subprocess.check_output(
            ["docker", "volume", "create", code_volume_name],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    except subprocess.CalledProcessError as exc:
        details = (exc.output or str(exc)).strip()[:200]
        log_agent(state["scan_id"], "VolumeCreator", "Code volume creation failed")
        return merge_state(
            state,
            {
                "phase": "volume_creation_failed",
                "errors": [*state["errors"], f"Failed to create Docker code volume: {details}"],
            },
        )
    except FileNotFoundError:
        log_agent(state["scan_id"], "VolumeCreator", "Docker CLI unavailable")
        return merge_state(
            state,
            {
                "phase": "volume_creation_failed",
                "errors": [*state["errors"], "Failed to create Docker code volume: docker executable not found"],
            },
        )

    volume_name = created_name or code_volume_name
    volumes = {
        "code": volume_name,
    }

    log_agent(state["scan_id"], "VolumeCreator", f"Code volume ready: {volume_name}")

    return merge_state(
        state,
        {
            "phase": "volumes_created",
            "docker_volumes": volumes,
            "repo_path": "/workspace/code",
        },
    )
