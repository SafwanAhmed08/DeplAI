from __future__ import annotations

from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def dependency_scanner_node(state: ScanState) -> ScanState:
    # Dependency scanner inspects requirements files and emits mock dependency risks.
    log_agent(state["scan_id"], "DependencyScanner", "Running dependency scan")

    repo_path = state["repo_path"]
    findings: list[dict] = []

    if repo_path:
        base = Path(repo_path)
        for dep_file in ["requirements.txt", "pyproject.toml"]:
            candidate = base / dep_file
            if candidate.exists() and candidate.is_file():
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                if "django==1." in content or "flask==0." in content:
                    findings.append(
                        {
                            "scanner": "dependency",
                            "type": "outdated_dependency",
                            "severity": "high",
                            "file": str(candidate),
                            "line": 1,
                            "message": "Potentially outdated dependency version detected",
                            "category_hint": "vulnerable_components",
                        }
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
