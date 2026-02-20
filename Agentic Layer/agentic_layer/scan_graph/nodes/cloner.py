from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
import os
from pathlib import Path
import shutil
from typing import Any

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _build_basic_auth_header(token: str) -> str:
    raw = f"x-access-token:{token}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"AUTHORIZATION: basic {encoded}"


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


async def _run_clone(
    repo_url: str,
    target_path: Path,
    token: str | None,
    use_auth_header: bool,
) -> tuple[bool, str]:
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        repo_url,
        str(target_path),
    ]

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"

    if use_auth_header and token:
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraheader"
        env["GIT_CONFIG_VALUE_0"] = _build_basic_auth_header(token)

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    if process.returncode == 0:
        return True, stdout or "clone succeeded"

    return False, stderr or stdout or "clone failed"


async def cloner_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    # Setup/acquisition step: clone code into prepared repository volume.
    log_agent(state["scan_id"], "Cloner", "Starting code acquisition")
    if state["repo_path"] is None:
        log_agent(state["scan_id"], "Cloner", "Repository path missing, cannot clone")
        return merge_state(
            state,
            {
                "phase": "clone_failed",
                "errors": [*state["errors"], "Repository path not initialized"],
            },
        )

    code_path = Path(state["repo_path"])
    repo_url = state["repo_url"]
    token = _token_from_config(config)

    if code_path.exists():
        for child in code_path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    # First attempt with auth header when a token is present.
    # If that fails, retry without auth to support public repositories with invalid/expired tokens.
    try:
        success, output = await asyncio.wait_for(
            _run_clone(repo_url=repo_url, target_path=code_path, token=token, use_auth_header=bool(token)),
            timeout=90,
        )
    except TimeoutError:
        log_agent(state["scan_id"], "Cloner", "Clone timed out")
        return merge_state(
            state,
            {
                "phase": "clone_failed",
                "errors": [*state["errors"], "Repository clone timed out"],
            },
        )
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Cloner", "Clone process failed to start")
        return merge_state(
            state,
            {
                "phase": "clone_failed",
                "errors": [*state["errors"], f"Repository clone failed to start: {str(exc)[:200]}"],
            },
        )

    if not success:
        if code_path.exists() and any(code_path.iterdir()):
            for child in code_path.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()

        retry_success, retry_output = await _run_clone(
            repo_url=repo_url,
            target_path=code_path,
            token=None,
            use_auth_header=False,
        )
        success = retry_success
        output = retry_output

    if not success:
        log_agent(state["scan_id"], "Cloner", "Clone failed")
        return merge_state(
            state,
            {
                "phase": "clone_failed",
                "errors": [*state["errors"], f"Repository clone failed: {output.strip()[:300]}"],
            },
        )

    log_agent(state["scan_id"], "Cloner", f"Clone complete at {code_path}")

    return merge_state(
        state,
        {
            "phase": "code_acquired",
        },
    )
