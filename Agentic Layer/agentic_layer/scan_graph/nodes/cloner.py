from __future__ import annotations

import asyncio
from collections.abc import Mapping
import json
import re
from typing import Any

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _token_from_config(config: dict[str, Any] | None) -> str | None:
    if not isinstance(config, Mapping):
        return None
    configurable = config.get("configurable", {})
    if not isinstance(configurable, Mapping):
        return None
    token = configurable.get("github_token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def _run_clone_in_volume(
    scan_id: str,
    repo_url: str,
    volume_name: str,
    token: str | None,
    use_auth_header: bool,
) -> dict[str, Any]:
    clone_script = (
        "set -eu; "
        "rm -rf /workspace/code/* /workspace/code/.[!.]* /workspace/code/..?* 2>/dev/null || true; "
        "mkdir -p /workspace/code; "
        "git clone --depth 1 \"$REPO_URL\" /workspace/code"
    )
    env = {"REPO_URL": repo_url}

    if use_auth_header and token:
        clone_script = (
            "set -eu; "
            "rm -rf /workspace/code/* /workspace/code/.[!.]* /workspace/code/..?* 2>/dev/null || true; "
            "mkdir -p /workspace/code; "
            "base=${REPO_URL#https://}; "
            "clone_url=\"https://x-access-token:${GITHUB_TOKEN}@${base}\"; "
            "git clone --depth 1 \"$clone_url\" /workspace/code"
        )
        env["GITHUB_TOKEN"] = token

    try:
        DockerExecutionHelper.run(
            scan_id=scan_id,
            image="alpine/git",
            entrypoint="sh",
            command=["-lc", clone_script],
            volume_name=volume_name,
            mount_path="/workspace/code",
            workdir="/workspace",
            read_only=False,
            network_none=False,
            timeout_seconds=90,
            env=env,
            component="Cloner",
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "reason": "git_clone_failed",
        }

    return {
        "success": True,
        "exit_code": 0,
        "stdout": "clone succeeded",
        "stderr": "",
        "reason": "clone_succeeded",
    }


def _clone_volume_with_optional_auth(
    scan_id: str,
    repo_url: str,
    volume_name: str,
    token: str | None,
) -> None:
    result = _run_clone_in_volume(
        scan_id=scan_id,
        repo_url=repo_url,
        volume_name=volume_name,
        token=token,
        use_auth_header=bool(token),
    )
    if result.get("success"):
        return

    retry_result = _run_clone_in_volume(
        scan_id=scan_id,
        repo_url=repo_url,
        volume_name=volume_name,
        token=None,
        use_auth_header=False,
    )
    if retry_result.get("success"):
        return

    raise RuntimeError(str(result.get("stderr") or result.get("stdout") or "clone failed"))


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    redacted = text
    patterns = [
        r"gh[pousr]_[A-Za-z0-9_]+",
        r"lsv2_[A-Za-z0-9_]+",
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+",
        r"(?i)(token\s*[=:]\s*)[^\s\"']+",
        r"https://x-access-token:[^@\s]+@",
    ]
    for pattern in patterns:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted[:3000]


async def cloner_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    # Setup/acquisition step: clone code into prepared Docker code volume.
    log_agent(state["scan_id"], "Cloner", "Starting code acquisition")
    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        log_agent(state["scan_id"], "Cloner", "Code volume missing, cannot clone")
        return merge_state(
            state,
            {
                "phase": "clone_failed",
                "errors": [*state["errors"], "Code Docker volume not initialized"],
            },
        )

    repo_url = state["repo_url"]
    token = _token_from_config(config)

    # Clone directly into Docker named volume.
    try:
        log_agent(state["scan_id"], "Cloner", "Cloning repository into Docker code volume")
        await asyncio.wait_for(
            asyncio.to_thread(
                _clone_volume_with_optional_auth,
                state["scan_id"],
                repo_url,
                code_volume_name,
                token,
            ),
            timeout=120,
        )
    except TimeoutError:
        log_agent(state["scan_id"], "Cloner", "Clone timed out")
        structured = {
            "component": "Cloner",
            "code": "CLONE_TIMEOUT",
            "reason": "Repository clone timed out",
            "exit_code": 124,
            "stderr": "",
        }
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], json.dumps(structured)],
            },
        )
    except RuntimeError as exc:
        log_agent(state["scan_id"], "Cloner", "Clone failed")
        structured = {
            "component": "Cloner",
            "code": "CLONE_FAILED",
            "reason": "git_clone_failed",
            "exit_code": 1,
            "stderr": _sanitize_text(str(exc)),
        }
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], json.dumps(structured)],
            },
        )
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Cloner", "Clone process failed to start")
        structured = {
            "component": "Cloner",
            "code": "CLONE_START_FAILED",
            "reason": "Repository clone failed to start",
            "exit_code": 1,
            "stderr": _sanitize_text(str(exc)),
        }
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], json.dumps(structured)],
            },
        )

    log_agent(state["scan_id"], "Cloner", "Code successfully loaded into volume")

    return merge_state(
        state,
        {
            "phase": "code_acquired",
        },
    )
