from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Mapping

from agentic_layer.scan_graph.logger import log_agent


@dataclass(frozen=True)
class DockerExecutionResult:
    exit_code: int
    stdout: str
    stderr: str


class DockerExecutionHelper:
    @staticmethod
    def run(
        *,
        scan_id: str,
        image: str,
        command: list[str],
        volume_name: str,
        entrypoint: str | None = None,
        mount_path: str = "/workspace",
        workdir: str = "/workspace",
        read_only: bool = True,
        network_none: bool = True,
        timeout_seconds: int = 120,
        env: Mapping[str, str] | None = None,
        component: str = "DockerExecution",
    ) -> DockerExecutionResult:
        mount = f"{volume_name}:{mount_path}"
        if read_only:
            mount = f"{mount}:ro"

        docker_cmd = ["docker", "run", "--rm"]
        if network_none:
            docker_cmd.extend(["--network", "none"])
        if entrypoint:
            docker_cmd.extend(["--entrypoint", entrypoint])
        docker_cmd.extend(["-v", mount, "-w", workdir])

        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        docker_cmd.extend([image, *command])

        log_agent(scan_id, component, f"Starting container command image={image}")
        try:
            completed = subprocess.run(
                docker_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Docker executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Container command timed out after {timeout_seconds}s") from exc

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        if completed.returncode != 0:
            details = (stderr or stdout or "docker command failed").strip()
            raise RuntimeError(f"Container command failed (exit_code={completed.returncode}): {details}")

        log_agent(scan_id, component, f"Container command succeeded image={image}")
        return DockerExecutionResult(
            exit_code=int(completed.returncode),
            stdout=stdout,
            stderr=stderr,
        )
