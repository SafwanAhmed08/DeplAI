from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def regex_scanner_node(state: ScanState) -> ScanState:
    # Regex scanner finds quick signal patterns across text files.
    log_agent(state["scan_id"], "RegexScanner", "Running regex scan")

    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], "Regex scanner failed: code Docker volume missing"],
            },
        )

    script = (
        "import json, pathlib, re\n"
        "patterns = [\n"
        "    (re.compile(r'AKIA[0-9A-Z]{16}'), 'potential_aws_key', 'high', 'security_misconfiguration'),\n"
        "    (re.compile(r\"password\\s*=\\s*['\\\"][^'\\\"]+['\\\"]\", re.IGNORECASE), 'hardcoded_password', 'high', 'broken_access_control'),\n"
        "    (re.compile(r'http://', re.IGNORECASE), 'insecure_transport', 'medium', 'cryptographic_failures'),\n"
        "]\n"
        "findings = []\n"
        "for file_path in pathlib.Path('/workspace').rglob('*'):\n"
        "    if not file_path.is_file():\n"
        "        continue\n"
        "    try:\n"
        "        content = file_path.read_text(encoding='utf-8', errors='ignore')\n"
        "    except Exception:\n"
        "        continue\n"
        "    for pattern, finding_type, severity, hint in patterns:\n"
        "        for match in pattern.finditer(content):\n"
        "            line = content.count('\\n', 0, match.start()) + 1\n"
        "            findings.append({\n"
        "                'scanner': 'regex',\n"
        "                'type': finding_type,\n"
        "                'severity': severity,\n"
        "                'file': str(file_path),\n"
        "                'line': int(line),\n"
        "                'message': f'Pattern matched: {finding_type}',\n"
        "                'evidence': match.group(0)[:120],\n"
        "                'category_hint': hint,\n"
        "            })\n"
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
            component="RegexScanner",
        )
        output_lines = (result.stdout or "").strip().splitlines()
        payload = json.loads(output_lines[-1] if output_lines else "{}")
        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise RuntimeError("Regex scanner returned invalid findings payload")
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], f"Regex scanner failed in container: {exc}"],
            },
        )

    raw_tool_outputs = [
        *state["raw_tool_outputs"],
        {
            "tool": "regex_scanner",
            "findings": findings,
            "summary": {"count": len(findings)},
        },
    ]

    log_agent(state["scan_id"], "RegexScanner", f"Regex scan complete with {len(findings)} findings")
    return merge_state(state, {"raw_tool_outputs": raw_tool_outputs, "analysis_stage": "regex_scanned"})
