from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def analysis_planner_node(state: ScanState) -> ScanState:
    # Planner decides what scanners to run based on repo characteristics.
    log_agent(state["scan_id"], "AnalysisPlanner", "Planning analysis scanner execution")

    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], "Analysis planner failed: code Docker volume missing"],
            },
        )

    script = (
        "import json, pathlib\n"
        "root = pathlib.Path('/workspace')\n"
        "has_python = any(p.suffix.lower() == '.py' for p in root.rglob('*') if p.is_file())\n"
        "has_requirements = any(p.name.lower() in {'requirements.txt', 'pyproject.toml', 'poetry.lock'} for p in root.rglob('*') if p.is_file())\n"
        "has_config_files = any(p.name.lower() in {'.env', 'config.yml', 'config.yaml', 'settings.json'} for p in root.rglob('*') if p.is_file())\n"
        "print(json.dumps({'has_python': has_python, 'has_requirements': has_requirements, 'has_config_files': has_config_files}))\n"
    )

    try:
        result = DockerExecutionHelper.run(
            scan_id=state["scan_id"],
            image="python:3.12-alpine",
            command=["python", "-c", script],
            volume_name=code_volume_name,
            mount_path="/workspace",
            workdir="/workspace",
            read_only=True,
            network_none=True,
            timeout_seconds=60,
            component="AnalysisPlanner",
        )
        output = (result.stdout or "").strip().splitlines()
        payload = json.loads(output[-1] if output else "{}")
        has_python = bool(payload.get("has_python", False))
        has_requirements = bool(payload.get("has_requirements", False))
        has_config_files = bool(payload.get("has_config_files", False))
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], f"Analysis planner failed in container: {exc}"],
            },
        )

    repo_metadata = dict(state["repo_metadata"])
    repo_metadata["analysis_plan"] = {
        "run_ast_scanner": has_python,
        "run_regex_scanner": True,
        "run_dependency_scanner": has_requirements,
        "run_config_scanner": has_config_files,
    }

    return merge_state(
        state,
        {
            "phase": "analysis",
            "analysis_stage": "planned",
            "repo_metadata": repo_metadata,
        },
    )
