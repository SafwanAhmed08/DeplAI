from __future__ import annotations

import subprocess

try:
    from docker import from_env as docker_from_env
    from docker.errors import NotFound as DockerNotFound
except Exception:  # noqa: BLE001
    docker_from_env = None

    class DockerNotFound(Exception):
        pass

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def volume_cleanup_node(state: ScanState) -> ScanState:
    cleanup_status = dict(state.get("cleanup_status", {}))

    if bool(cleanup_status.get("volume_removed")):
        log_agent(state["scan_id"], "VolumeCleanup", "Volume already removed; skipping")
        return merge_state(state, {"cleanup_status": cleanup_status})

    volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not volume_name:
        cleanup_status["volume_removed"] = True
        return merge_state(state, {"cleanup_status": cleanup_status})

    try:
        if docker_from_env is not None:
            client = docker_from_env()
            try:
                volume = client.volumes.get(volume_name)
                volume.remove(force=True)
                cleanup_status["volume_removed"] = True
                log_agent(state["scan_id"], "VolumeCleanup", f"Removed volume {volume_name}")
            except DockerNotFound:
                cleanup_status["volume_removed"] = True
                log_agent(state["scan_id"], "VolumeCleanup", f"Volume not found {volume_name}; skipping")
            finally:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass
            return merge_state(state, {"cleanup_status": cleanup_status})

        completed = subprocess.run(
            ["docker", "volume", "rm", "-f", volume_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        no_such_volume = "No such volume" in output

        if completed.returncode == 0 or no_such_volume:
            cleanup_status["volume_removed"] = True
            log_agent(state["scan_id"], "VolumeCleanup", f"Removed volume {volume_name}")
        else:
            log_agent(
                state["scan_id"],
                "VolumeCleanup",
                f"Volume removal failed for {volume_name}; continuing cleanup: {output[:240]}",
            )
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, DockerNotFound):
            cleanup_status["volume_removed"] = True
            log_agent(state["scan_id"], "VolumeCleanup", f"Volume not found {volume_name}; skipping")
        else:
            log_agent(
                state["scan_id"],
                "VolumeCleanup",
                f"Volume cleanup exception for {volume_name}; continuing cleanup: {exc}",
            )

    return merge_state(
        state,
        {
            "cleanup_status": cleanup_status,
        },
    )
