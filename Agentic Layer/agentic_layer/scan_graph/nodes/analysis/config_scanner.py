from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def config_scanner_node(state: ScanState) -> ScanState:
    # Config scanner checks obvious insecure configuration signs.
    log_agent(state["scan_id"], "ConfigScanner", "Running config scan")

    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], "Config scanner failed: code Docker volume missing"],
            },
        )

    script = (
        "import json, pathlib\n"
        "targets = {'.env', 'config.yaml', 'config.yml', 'settings.json', 'docker-compose.yml'}\n"
        "findings = []\n"
        "for file_path in pathlib.Path('/workspace').rglob('*'):\n"
        "    if not file_path.is_file():\n"
        "        continue\n"
        "    if file_path.name.lower() not in targets:\n"
        "        continue\n"
        "    content = file_path.read_text(encoding='utf-8', errors='ignore')\n"
        "    if 'DEBUG=true' in content or 'debug: true' in content.lower():\n"
        "        findings.append({\n"
        "            'scanner': 'config',\n"
        "            'type': 'debug_mode_enabled',\n"
        "            'severity': 'medium',\n"
        "            'file': str(file_path),\n"
        "            'line': 1,\n"
        "            'message': 'Debug mode appears enabled in configuration',\n"
        "            'category_hint': 'security_misconfiguration',\n"
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
            component="ConfigScanner",
        )
        output_lines = (result.stdout or "").strip().splitlines()
        payload = json.loads(output_lines[-1] if output_lines else "{}")
        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise RuntimeError("Config scanner returned invalid findings payload")
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], f"Config scanner failed in container: {exc}"],
            },
        )

    raw_tool_outputs = [
        *state["raw_tool_outputs"],
        {
            "tool": "config_scanner",
            "findings": findings,
            "summary": {"count": len(findings)},
        },
    ]

    log_agent(state["scan_id"], "ConfigScanner", f"Config scan complete with {len(findings)} findings")
    return merge_state(state, {"raw_tool_outputs": raw_tool_outputs, "analysis_stage": "config_scanned"})
