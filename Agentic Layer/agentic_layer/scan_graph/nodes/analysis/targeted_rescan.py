from __future__ import annotations

from typing import Awaitable
from typing import Callable

from agentic_layer.scan_graph.nodes.analysis.ast_scanner import ast_scanner_node
from agentic_layer.scan_graph.nodes.analysis.config_scanner import config_scanner_node
from agentic_layer.scan_graph.nodes.analysis.dependency_scanner import dependency_scanner_node
from agentic_layer.scan_graph.nodes.analysis.regex_scanner import regex_scanner_node
from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


SCANNER_BY_GAP: dict[str, tuple[str, Callable[[ScanState], Awaitable[ScanState]]]] = {
    "ast": ("ast_scanner", ast_scanner_node),
    "regex": ("regex_scanner", regex_scanner_node),
    "dependency": ("dependency_scanner", dependency_scanner_node),
    "config": ("config_scanner", config_scanner_node),
}

VALID_SEVERITIES = {"critical", "high", "medium", "low", "info", "informational"}


def _severity_origin(source_tool: str, finding: dict) -> str:
    finding_type = str(finding.get("type") or "unknown").strip().lower().replace(" ", "_")
    return f"{source_tool}_rule_{finding_type}"


def _evidence_ref(finding: dict) -> str:
    file_path = str(finding.get("file") or finding.get("file_path") or "")
    line_number = int(finding.get("line") or finding.get("line_number") or 0)
    if file_path and line_number > 0:
        return f"{file_path}:{line_number}"
    if file_path:
        return file_path
    return ""


def _normalize_rescan_finding(source_tool: str, finding: dict) -> dict | None:
    raw_source = str(finding.get("source") or "").strip().lower()
    if raw_source in {"synthetic", "mock"}:
        return None

    evidence_ref = _evidence_ref(finding)
    if not evidence_ref:
        return None

    normalized = dict(finding)
    normalized["source_tool"] = source_tool
    normalized["evidence_ref"] = evidence_ref
    normalized["evidence"] = str(normalized.get("evidence") or normalized.get("message") or evidence_ref)

    severity = str(normalized.get("severity") or "low").strip().lower()
    normalized["severity"] = severity if severity in VALID_SEVERITIES else "low"
    normalized["severity_origin"] = _severity_origin(source_tool, normalized)

    category_hint = str(normalized.get("category_hint") or "").strip().lower()
    if category_hint in {"", "unknown", "general", "placeholder"}:
        return None

    return normalized


async def targeted_rescan_node(state: ScanState) -> ScanState:
    # Targeted rescan re-runs real scanners for identified coverage gaps.
    log_agent(state["scan_id"], "TargetedRescan", "Running targeted rescan for coverage gaps")

    gaps = [str(gap).strip().lower() for gap in state["coverage_gaps"]]
    runnable = [gap for gap in gaps if gap in SCANNER_BY_GAP]

    if not runnable:
        log_agent(state["scan_id"], "TargetedRescan", "No-op: no runnable gaps for targeted rescan")
        return merge_state(
            state,
            {
                "rescans_triggered": True,
                "coverage_gaps": [],
                "analysis_stage": "rescanned",
            },
        )

    starting_outputs_count = len(state["raw_tool_outputs"])
    rescanned_state = state
    for gap in runnable:
        tool_name, scanner_node = SCANNER_BY_GAP[gap]
        log_agent(state["scan_id"], "TargetedRescan", f"Re-running {tool_name} for gap={gap}")
        rescanned_state = await scanner_node(rescanned_state)

    new_outputs = list(rescanned_state["raw_tool_outputs"][starting_outputs_count:])
    normalized_outputs: list[dict] = []
    normalized_finding_count = 0
    for output in new_outputs:
        source_tool = str(output.get("tool") or "")
        findings = output.get("findings") if isinstance(output.get("findings"), list) else []
        normalized_findings = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            normalized = _normalize_rescan_finding(source_tool, finding)
            if normalized is None:
                continue
            normalized_findings.append(normalized)

        normalized_finding_count += len(normalized_findings)
        normalized_outputs.append(
            {
                **output,
                "findings": normalized_findings,
                "summary": {
                    **(output.get("summary") if isinstance(output.get("summary"), dict) else {}),
                    "normalized_count": len(normalized_findings),
                    "rescan_gap": source_tool,
                },
            }
        )

    if normalized_finding_count == 0:
        log_agent(state["scan_id"], "TargetedRescan", "No-op: targeted rescan produced no additional evidence")
        return merge_state(
            state,
            {
                "rescans_triggered": True,
                "coverage_gaps": [],
                "analysis_stage": "rescanned",
            },
        )

    log_agent(state["scan_id"], "TargetedRescan", f"Targeted rescan complete with {normalized_finding_count} evidence-backed findings")
    return merge_state(
        state,
        {
            "raw_tool_outputs": [*state["raw_tool_outputs"], *normalized_outputs],
            "rescans_triggered": True,
            "coverage_gaps": [],
            "analysis_stage": "rescanned",
        },
    )
