from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".js": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}


async def codebase_stats_node(state: ScanState) -> ScanState:
    # Computes file counts, total size, and language breakdown.
    log_agent(state["scan_id"], "CodebaseStats", "Computing codebase statistics")
    repo_metadata = dict(state["repo_metadata"])
    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()

    if not code_volume_name:
        log_agent(state["scan_id"], "CodebaseStats", "Code volume missing, stats failed")
        return merge_state(
            state,
            {
                "phase": "stats_failed",
                "errors": [*state["errors"], "Code Docker volume missing for stats"],
            },
        )

    try:
        result = DockerExecutionHelper.run(
            scan_id=state["scan_id"],
            image="alpine",
            command=[
                "sh",
                "-lc",
                "files=$(find /workspace -type f | wc -l); "
                "size_kb=$(du -sk /workspace | awk '{print $1}'); "
                "printf '{\"total_files\":%s,\"total_size_bytes\":%s}\n' \"$files\" \"$((size_kb*1024))\"",
            ],
            volume_name=code_volume_name,
            mount_path="/workspace",
            workdir="/workspace",
            read_only=True,
            network_none=True,
            timeout_seconds=60,
            component="CodebaseStats",
        )
        output = (result.stdout or "").strip().splitlines()
        payload = json.loads(output[-1] if output else "{}")
        total_files = int(payload.get("total_files", 0))
        total_size_bytes = int(payload.get("total_size_bytes", 0))
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "stats_failed",
                "errors": [*state["errors"], f"Codebase stats failed in container: {exc}"],
            },
        )

    repo_metadata["stats"] = {
        "total_files": total_files,
        "total_size_bytes": total_size_bytes,
        "language_breakdown": {},
    }
    log_agent(
        state["scan_id"],
        "CodebaseStats",
        f"Stats complete: files={total_files}, size_bytes={total_size_bytes}",
    )

    return merge_state(
        state,
        {
            "phase": "stats_computed",
            "repo_metadata": repo_metadata,
        },
    )
