from __future__ import annotations

import ast
from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def ast_scanner_node(state: ScanState) -> ScanState:
    # Mock AST scanner for Python files. Flags risky calls and exec/eval patterns.
    log_agent(state["scan_id"], "ASTScanner", "Running AST scan")

    repo_path = state["repo_path"]
    if not repo_path:
        return merge_state(state, {"analysis_stage": "ast_scanned"})

    findings: list[dict] = []
    for file_path in Path(repo_path).rglob("*.py"):
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in {"eval", "exec"}:
                    findings.append(
                        {
                            "scanner": "ast",
                            "type": "dynamic_execution",
                            "severity": "high",
                            "file": str(file_path),
                            "line": getattr(node, "lineno", 1),
                            "message": f"Use of {func_name} detected",
                            "category_hint": "injection",
                        }
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
