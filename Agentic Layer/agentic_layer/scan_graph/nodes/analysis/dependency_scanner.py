from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def dependency_scanner_node(state: ScanState) -> ScanState:
    # Dependency scanner inspects requirements files and emits mock dependency risks.
    log_agent(state["scan_id"], "DependencyScanner", "Running dependency scan")

    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], "Dependency scanner failed: code Docker volume missing"],
            },
        )

    script = (
        "import json, pathlib\n"
        "root = pathlib.Path('/workspace')\n"
        "findings = []\n"
        "for dep_file in ['requirements.txt', 'pyproject.toml']:\n"
        "    candidate = root / dep_file\n"
        "    if not candidate.exists() or not candidate.is_file():\n"
        "        continue\n"
        "    content = candidate.read_text(encoding='utf-8', errors='ignore')\n"
        "    if 'django==1.' in content or 'flask==0.' in content:\n"
        "        findings.append({\n"
        "            'scanner': 'dependency',\n"
        "            'type': 'outdated_dependency',\n"
        "            'severity': 'high',\n"
        "            'file': str(candidate),\n"
        "            'line': 1,\n"
        "            'message': 'Potentially outdated dependency version detected',\n"
        "            'category_hint': 'vulnerable_components',\n"
        "        })\n"
        "print(json.dumps({'findings': findings, 'summary': {'count': len(findings)}}))\n"
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
            timeout_seconds=120,
            component="DependencyScanner",
        )
        output_lines = (result.stdout or "").strip().splitlines()
        payload = json.loads(output_lines[-1] if output_lines else "{}")
        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise RuntimeError("Dependency scanner returned invalid findings payload")
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], f"Dependency scanner failed in container: {exc}"],
            },
        )

    raw_tool_outputs = [
        *state["raw_tool_outputs"],
        {
            "tool": "dependency_scanner",
            "findings": findings,
            "summary": {"count": len(findings)},
        },
    ]

    log_agent(state["scan_id"], "DependencyScanner", f"Dependency scan complete with {len(findings)} findings")
    return merge_state(state, {"raw_tool_outputs": raw_tool_outputs, "analysis_stage": "dependency_scanned"})
