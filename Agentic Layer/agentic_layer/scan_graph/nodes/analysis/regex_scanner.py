from __future__ import annotations

import re
from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "potential_aws_key", "high", "security_misconfiguration"),
    (re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE), "hardcoded_password", "high", "broken_access_control"),
    (re.compile(r"http://", re.IGNORECASE), "insecure_transport", "medium", "cryptographic_failures"),
]


async def regex_scanner_node(state: ScanState) -> ScanState:
    # Regex scanner finds quick signal patterns across text files.
    log_agent(state["scan_id"], "RegexScanner", "Running regex scan")

    repo_path = state["repo_path"]
    if not repo_path:
        return merge_state(state, {"analysis_phase": "regex_scanned"})

    findings: list[dict] = []
    for file_path in Path(repo_path).rglob("*"):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern, finding_type, severity, hint in PATTERNS:
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                findings.append(
                    {
                        "scanner": "regex",
                        "type": finding_type,
                        "severity": severity,
                        "file": str(file_path),
                        "line": line,
                        "message": f"Pattern matched: {finding_type}",
                        "evidence": match.group(0)[:120],
                        "category_hint": hint,
                    }
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
    return merge_state(state, {"raw_tool_outputs": raw_tool_outputs, "analysis_phase": "regex_scanned"})
