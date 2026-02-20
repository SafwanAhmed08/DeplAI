from __future__ import annotations

from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def config_scanner_node(state: ScanState) -> ScanState:
    # Config scanner checks obvious insecure configuration signs.
    log_agent(state["scan_id"], "ConfigScanner", "Running config scan")

    repo_path = state["repo_path"]
    findings: list[dict] = []

    if repo_path:
        for file_path in Path(repo_path).rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.name.lower() not in {".env", "config.yaml", "config.yml", "settings.json", "docker-compose.yml"}:
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if "DEBUG=true" in content or "debug: true" in content.lower():
                findings.append(
                    {
                        "scanner": "config",
                        "type": "debug_mode_enabled",
                        "severity": "medium",
                        "file": str(file_path),
                        "line": 1,
                        "message": "Debug mode appears enabled in configuration",
                        "category_hint": "security_misconfiguration",
                    }
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
