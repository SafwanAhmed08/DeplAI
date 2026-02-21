from __future__ import annotations

import asyncio
from collections.abc import Mapping
import json
import re
import subprocess
import time
from typing import Any
from urllib.parse import urlparse

import httpx

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
    timeout_seconds: int,
) -> dict[str, Any]:
    clone_script = (
        "set -eu; "
        "rm -rf /workspace/code/* /workspace/code/.[!.]* /workspace/code/..?* 2>/dev/null || true; "
        "mkdir -p /workspace/code; "
        "git clone --depth 1 --single-branch --no-tags --recurse-submodules=no \"$REPO_URL\" /workspace/code"
    )
    env = {
        "REPO_URL": repo_url,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "echo",
    }

    if use_auth_header and token:
        clone_script = (
            "set -eu; "
            "rm -rf /workspace/code/* /workspace/code/.[!.]* /workspace/code/..?* 2>/dev/null || true; "
            "mkdir -p /workspace/code; "
            "git -c http.extraheader=\"Authorization: Bearer ${GITHUB_TOKEN}\" "
            "clone --depth 1 --single-branch --no-tags --recurse-submodules=no \"$REPO_URL\" /workspace/code"
        )
        env["GITHUB_TOKEN"] = token

    container_name = f"deplai_clone_{re.sub(r'[^a-zA-Z0-9_.-]', '_', scan_id).lower()}_{int(time.time())}"
    docker_cmd = [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "--entrypoint",
        "sh",
        "-v",
        f"{volume_name}:/workspace/code",
        "-w",
        "/workspace",
    ]
    for key, value in env.items():
        docker_cmd.extend(["-e", f"{key}={value}"])
    docker_cmd.extend(["alpine/git", "-lc", clone_script])

    log_agent(scan_id, "Cloner", "Starting container command image=alpine/git")
    log_agent(
        scan_id,
        "Cloner",
        "Clone command: git clone --depth 1 --single-branch --no-tags --recurse-submodules=no <repo_url> /workspace/code",
    )
    try:
        completed = subprocess.run(
            docker_cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if stdout.strip():
            log_agent(scan_id, "Cloner", f"Clone stdout: {_sanitize_text(stdout)[:1200]}")
        if stderr.strip():
            log_agent(scan_id, "Cloner", f"Clone stderr: {_sanitize_text(stderr)[:1200]}")

        if completed.returncode != 0:
            return {
                "success": False,
                "exit_code": int(completed.returncode),
                "stdout": _sanitize_text(stdout),
                "stderr": _sanitize_text(stderr),
                "reason": "git_clone_failed",
            }
    except subprocess.TimeoutExpired as exc:
        try:
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception:  # noqa: BLE001
            pass
        timeout_stdout = _sanitize_text((exc.stdout or "").decode("utf-8", errors="ignore") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        timeout_stderr = _sanitize_text((exc.stderr or "").decode("utf-8", errors="ignore") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
        if timeout_stdout:
            log_agent(scan_id, "Cloner", f"Clone timeout stdout: {timeout_stdout[:1200]}")
        if timeout_stderr:
            log_agent(scan_id, "Cloner", f"Clone timeout stderr: {timeout_stderr[:1200]}")
        return {
            "success": False,
            "exit_code": 124,
            "stdout": timeout_stdout,
            "stderr": timeout_stderr or f"Container command timed out after {timeout_seconds}s",
            "reason": "git_clone_timeout",
        }
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
    timeout_seconds: int,
) -> None:
    result = _run_clone_in_volume(
        scan_id=scan_id,
        repo_url=repo_url,
        volume_name=volume_name,
        token=token,
        use_auth_header=bool(token),
        timeout_seconds=timeout_seconds,
    )
    if result.get("success"):
        return

    retry_result = _run_clone_in_volume(
        scan_id=scan_id,
        repo_url=repo_url,
        volume_name=volume_name,
        token=None,
        use_auth_header=False,
        timeout_seconds=timeout_seconds,
    )
    if retry_result.get("success"):
        return

    raise RuntimeError(str(result.get("stderr") or result.get("stdout") or "clone failed"))


def _extract_owner_repo(repo_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(repo_url)
    if "github.com" not in parsed.netloc.lower():
        return None, None

    parts = [segment for segment in parsed.path.strip("/").split("/") if segment]
    if len(parts) < 2:
        return None, None

    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None, None
    return owner, repo


def _compute_dynamic_timeout(repo_size_kb: int, base_timeout: int = 120, max_timeout: int = 600) -> int:
    dynamic_timeout = int(base_timeout + (float(repo_size_kb) / 50.0))
    return max(base_timeout, min(max_timeout, dynamic_timeout))


async def _resolve_clone_timeout_seconds(scan_id: str, repo_url: str, token: str | None) -> int:
    base_timeout = 120
    owner, repo = _extract_owner_repo(repo_url)
    if not owner or not repo:
        log_agent(scan_id, "Cloner", "Unable to parse owner/repo for timeout sizing; using base timeout=120s")
        return base_timeout

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "deplai-agent/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if response.status_code != 200:
            log_agent(
                scan_id,
                "Cloner",
                f"Repo size lookup failed status={response.status_code}; using base timeout=120s",
            )
            return base_timeout

        payload = response.json() if isinstance(response.json(), dict) else {}
        repo_size_kb = int(payload.get("size") or 0)
        timeout_seconds = _compute_dynamic_timeout(repo_size_kb=repo_size_kb, base_timeout=base_timeout, max_timeout=600)
        log_agent(
            scan_id,
            "Cloner",
            f"Repo size resolved repo_size_kb={repo_size_kb} timeout_seconds={timeout_seconds}",
        )
        return timeout_seconds
    except Exception as exc:  # noqa: BLE001
        log_agent(scan_id, "Cloner", f"Repo size lookup failed ({exc}); using base timeout=120s")
        return base_timeout


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
    timeout_seconds = await _resolve_clone_timeout_seconds(state["scan_id"], repo_url, token)

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
                timeout_seconds,
            ),
            timeout=max(timeout_seconds + 10, 130),
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
