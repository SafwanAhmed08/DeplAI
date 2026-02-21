from __future__ import annotations

import json

from agentic_layer.runtime.docker_execution import DockerExecutionHelper
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _validate_findings(findings: list[dict]) -> None:
    required = {"scanner", "type", "severity", "file", "line", "message", "category_hint"}
    for finding in findings:
        if not isinstance(finding, dict):
            raise RuntimeError("AST scanner returned non-dict finding")
        missing = required.difference(finding.keys())
        if missing:
            raise RuntimeError(f"AST scanner finding missing keys: {sorted(missing)}")


async def ast_scanner_node(state: ScanState) -> ScanState:
    # Mock AST scanner for Python files. Flags risky calls and exec/eval patterns.
    log_agent(state["scan_id"], "ASTScanner", "Running AST scan")

    code_volume_name = str(state.get("docker_volumes", {}).get("code", "")).strip()
    if not code_volume_name:
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], "AST scanner failed: code Docker volume missing"],
            },
        )

    script = (
        "import ast, json, pathlib\n"
        "root = pathlib.Path('/workspace')\n"
        "findings = []\n"
        "for file_path in root.rglob('*.py'):\n"
        "    try:\n"
        "        source = file_path.read_text(encoding='utf-8', errors='ignore')\n"
        "        tree = ast.parse(source)\n"
        "    except Exception:\n"
        "        continue\n"
        "    for node in ast.walk(tree):\n"
        "        if isinstance(node, ast.Call):\n"
        "            func_name = ''\n"
        "            if isinstance(node.func, ast.Name):\n"
        "                func_name = node.func.id\n"
        "            elif isinstance(node.func, ast.Attribute):\n"
        "                func_name = node.func.attr\n"
        "            if func_name in {'eval', 'exec'}:\n"
        "                findings.append({\n"
        "                    'scanner': 'ast',\n"
        "                    'type': 'dynamic_execution',\n"
        "                    'severity': 'high',\n"
        "                    'file': str(file_path),\n"
        "                    'line': int(getattr(node, 'lineno', 1)),\n"
        "                    'message': f'Use of {func_name} detected',\n"
        "                    'category_hint': 'injection',\n"
        "                })\n"
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
            component="ASTScanner",
        )
        output_lines = (result.stdout or "").strip().splitlines()
        payload = json.loads(output_lines[-1] if output_lines else "{}")
        findings = payload.get("findings", [])
        if not isinstance(findings, list):
            raise RuntimeError("AST scanner returned invalid findings payload")
        _validate_findings(findings)
    except Exception as exc:  # noqa: BLE001
        return merge_state(
            state,
            {
                "phase": "error",
                "errors": [*state["errors"], f"AST scanner failed in container: {exc}"],
            },
        )

    raw_tool_outputs = [
        *state["raw_tool_outputs"],
        {
            "tool": "ast_scanner",
            "findings": findings,
            "summary": {"count": len(findings)},
        },
    ]

    log_agent(state["scan_id"], "ASTScanner", f"AST scan complete with {len(findings)} findings")
    return merge_state(state, {"raw_tool_outputs": raw_tool_outputs, "analysis_stage": "ast_scanned"})
