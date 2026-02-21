from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _parse_iso8601(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _build_phase_durations(state: ScanState) -> dict[str, float]:
    phase_timeline = list(state.get("phase_timeline", []))
    starts: dict[str, datetime] = {}
    durations: dict[str, float] = {}

    for entry in phase_timeline:
        phase = str(entry.get("phase", "")).strip()
        event = str(entry.get("event", "")).strip().lower()
        at_str = entry.get("at")
        if not phase or not isinstance(at_str, str):
            continue
        at_dt = _parse_iso8601(at_str)
        if at_dt is None:
            continue
        if event in {"started", "running", "initialized"} and phase not in starts:
            starts[phase] = at_dt
        if event in {"completed", "failed", "skipped"} and phase in starts:
            durations[phase] = max(0.0, round((at_dt - starts[phase]).total_seconds(), 3))

    return durations


def _tool_runtime_stats(state: ScanState) -> dict[str, Any]:
    execution_records = []
    for item in state.get("layer6_results", []):
        execution_records.extend(item.get("execution_record", []))

    total_tools = len(execution_records)
    total_runtime_ms = sum(int(rec.get("execution_time", 0)) for rec in execution_records)
    failed_tools = sum(1 for rec in execution_records if str(rec.get("status", "")) != "completed")

    return {
        "total_tools_executed": total_tools,
        "avg_tool_runtime_ms": round(total_runtime_ms / total_tools, 3) if total_tools else 0.0,
        "failed_tools": failed_tools,
    }


def _docker_operations_count(state: ScanState) -> int:
    tool_runs = 0
    for item in state.get("layer6_results", []):
        tool_runs += len(item.get("execution_record", []))

    setup_ops = 1 if state.get("docker_volumes", {}).get("code") else 0
    cleanup_ops = 1 if state.get("cleanup_status", {}).get("volume_removed") else 0
    clone_ops = 1
    return tool_runs + setup_ops + cleanup_ops + clone_ops


def _severity_weight(severity: str) -> float:
    normalized = severity.lower()
    if normalized == "critical":
        return 1.0
    if normalized == "high":
        return 0.85
    if normalized == "medium":
        return 0.55
    if normalized == "low":
        return 0.25
    return 0.1


def _emit_optional_shannon_event(state: ScanState) -> None:
    try:
        from shannon import emit_event  # type: ignore

        emit_event(
            "scan_observability_record",
            {
                "scan_id": state["scan_id"],
                "telemetry": state.get("telemetry", {}),
                "audit_record": state.get("audit_record", {}),
            },
        )
    except Exception:  # noqa: BLE001
        return


async def structured_scan_telemetry_node(state: ScanState) -> ScanState:
    telemetry = dict(state.get("telemetry", {}))

    try:
        phase_timeline = list(state.get("phase_timeline", []))
        started_at = _parse_iso8601(phase_timeline[0]["at"]) if phase_timeline else None
        total_duration = 0.0
        if started_at is not None:
            total_duration = max(0.0, round((datetime.now(timezone.utc) - started_at).total_seconds(), 3))

        categories_triggered = [
            str(item.get("category", "")).strip()
            for item in state.get("layer6_results", [])
            if str(item.get("category", "")).strip()
        ]
        categories_low_confidence = [
            str(item.get("category", "")).strip()
            for item in state.get("layer6_results", [])
            if str(item.get("category_status", "")) == "low_confidence"
        ]

        telemetry["scan_summary"] = {
            "total_duration_s": total_duration,
            "phase_durations": _build_phase_durations(state),
            "total_findings": len(state.get("intelligent_findings", [])),
            "categories_triggered": categories_triggered,
            "categories_low_confidence": categories_low_confidence,
            "docker_operations_count": _docker_operations_count(state),
            "tool_runtime_stats": _tool_runtime_stats(state),
        }

        log_agent(state["scan_id"], "Layer10", "Telemetry summary built")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer10", f"Telemetry summary failed: {exc}")

    return merge_state(state, {"telemetry": telemetry})


async def execution_intelligence_summary_node(state: ScanState) -> ScanState:
    telemetry = dict(state.get("telemetry", {}))

    try:
        findings = list(state.get("intelligent_findings", []))
        if findings:
            risk_profile_score = round(
                sum(_severity_weight(str(item.get("severity", ""))) for item in findings) / len(findings),
                3,
            )
        else:
            risk_profile_score = 0.0

        categories = [
            str(item.get("category", "")).strip()
            for item in state.get("layer6_results", [])
            if str(item.get("category", "")).strip()
        ]

        weighted_confidence_sum = 0.0
        weighted_count_sum = 0.0
        for item in state.get("layer6_results", []):
            confidence = float(item.get("category_confidence", 0.0))
            weight = max(1, len(item.get("aggregated_findings", [])))
            weighted_confidence_sum += confidence * weight
            weighted_count_sum += weight
        confidence_score = round(weighted_confidence_sum / weighted_count_sum, 3) if weighted_count_sum else 0.0

        regex_count = 0
        for output in state.get("raw_tool_outputs", []):
            if str(output.get("tool", "")) == "regex_scanner":
                regex_count += len(output.get("findings", []))
        validated_count = len(findings)
        noise_ratio = round(regex_count / max(1, validated_count), 3)

        telemetry["intelligence_summary"] = {
            "risk_profile_score": max(0.0, min(1.0, risk_profile_score)),
            "attack_surface_summary": {
                "categories": categories,
                "category_count": len(categories),
            },
            "confidence_score": max(0.0, min(1.0, confidence_score)),
            "noise_ratio": noise_ratio,
        }

        log_agent(state["scan_id"], "Layer10", "Intelligence score computed")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer10", f"Intelligence summary failed: {exc}")

    return merge_state(state, {"telemetry": telemetry})


async def structured_audit_record_node(state: ScanState) -> ScanState:
    audit_record = dict(state.get("audit_record", {}))

    if audit_record:
        return merge_state(state, {"audit_record": audit_record})

    try:
        project_meta = state.get("repo_metadata", {}).get("project", {})
        project_id = project_meta.get("project_id") if isinstance(project_meta, dict) else None
        tools_executed = []
        for result in state.get("layer6_results", []):
            for record in result.get("execution_record", []):
                tool_name = str(record.get("tool_name", "")).strip()
                if tool_name:
                    tools_executed.append(tool_name)

        audit_record = {
            "scan_id": state["scan_id"],
            "project_id": project_id or "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_path": [entry.get("phase") for entry in state.get("phase_timeline", []) if entry.get("phase")],
            "tools_executed": tools_executed,
            "cleanup_performed": bool(state.get("cleanup_status", {}).get("volume_removed")),
            "errors_count": len(state.get("errors", [])),
            "final_status": "completed" if bool(state.get("cleanup_status", {}).get("persistence_completed")) else "failed",
        }

        shannon_state = dict(state)
        shannon_state["audit_record"] = audit_record
        _emit_optional_shannon_event(shannon_state)  # type: ignore[arg-type]
        log_agent(state["scan_id"], "Layer10", "Audit record created")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer10", f"Audit record creation failed: {exc}")

    return merge_state(
        state,
        {
            "audit_record": audit_record,
        },
    )
