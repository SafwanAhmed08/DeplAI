from __future__ import annotations

from collections import Counter
from datetime import datetime
from datetime import timezone
from typing import Any

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _safe_categories(state: ScanState) -> list[str]:
    categories = [
        str(item.get("category", "")).strip()
        for item in state.get("layer6_results", [])
        if str(item.get("category", "")).strip()
    ]
    if categories:
        return sorted(set(categories))

    mapped = state.get("owasp_mapped", {})
    if isinstance(mapped, dict):
        return sorted([str(key) for key in mapped.keys() if str(key).strip()])
    return []


def _risk_distribution(findings: list[dict[str, Any]]) -> dict[str, int]:
    severities = [str(item.get("severity", "unknown")).lower() for item in findings]
    counter = Counter(severities)
    return {
        "critical": int(counter.get("critical", 0)),
        "high": int(counter.get("high", 0)),
        "medium": int(counter.get("medium", 0)),
        "low": int(counter.get("low", 0)),
        "unknown": int(counter.get("unknown", 0)),
    }


def _risk_level_from_distribution(dist: dict[str, int]) -> str:
    if dist.get("critical", 0) > 0 or dist.get("high", 0) >= 5:
        return "high"
    if dist.get("high", 0) > 0 or dist.get("medium", 0) >= 5:
        return "medium"
    return "low"


def _confidence_level(state: ScanState) -> str:
    score = float(state.get("telemetry", {}).get("intelligence_summary", {}).get("confidence_score", 0.0))
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _recommended_next_action(risk_level: str, requires_manual_review: bool) -> str:
    if risk_level == "high":
        return "prioritize_immediate_triage_and_remediation"
    if requires_manual_review:
        return "perform_manual_security_review"
    if risk_level == "medium":
        return "schedule_targeted_hardening_and_rescan"
    return "maintain_baseline_monitoring"


def _primary_risk_area(findings: list[dict[str, Any]], categories: list[str]) -> str:
    counter = Counter(str(item.get("category", "")).strip() for item in findings if str(item.get("category", "")).strip())
    if counter:
        return counter.most_common(1)[0][0]
    return categories[0] if categories else "none"


def _slack_webhook_stub(payload: dict[str, Any], enabled: bool = False) -> None:
    if not enabled:
        return


def _jira_ticket_creation_stub(payload: dict[str, Any], enabled: bool = False) -> None:
    if not enabled:
        return


def _github_security_alert_stub(payload: dict[str, Any], enabled: bool = False) -> None:
    if not enabled:
        return


def _email_notifier_stub(payload: dict[str, Any], enabled: bool = False) -> None:
    if not enabled:
        return


async def executive_summary_builder_node(state: ScanState) -> ScanState:
    external_report = dict(state.get("external_report", {}))

    try:
        findings = list(state.get("intelligent_findings", []))
        total_findings = len(findings)
        distribution = _risk_distribution(findings)
        categories = _safe_categories(state)
        risk_level = _risk_level_from_distribution(distribution)
        confidence_level = _confidence_level(state)

        low_confidence_categories = [
            str(item.get("category", "")).strip()
            for item in state.get("layer6_results", [])
            if str(item.get("category_status", "")) == "low_confidence"
        ]

        requires_manual_review = bool(low_confidence_categories) or risk_level == "high"
        executive_summary = {
            "risk_level": risk_level,
            "total_findings": total_findings,
            "critical_findings": int(distribution.get("critical", 0)),
            "owasp_categories": categories,
            "primary_risk_area": _primary_risk_area(findings, categories),
            "confidence_level": confidence_level,
            "recommended_next_action": _recommended_next_action(risk_level, requires_manual_review),
        }

        external_report["executive_summary"] = executive_summary
        log_agent(state["scan_id"], "Layer11", "Executive summary built")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer11", f"Executive summary build failed: {exc}")

    return merge_state(state, {"external_report": external_report})


async def security_posture_builder_node(state: ScanState) -> ScanState:
    external_report = dict(state.get("external_report", {}))

    try:
        findings = list(state.get("intelligent_findings", []))
        distribution = _risk_distribution(findings)
        categories = _safe_categories(state)
        category_confidence_map = {
            str(item.get("category", "")).strip(): float(item.get("category_confidence", 0.0))
            for item in state.get("layer6_results", [])
            if str(item.get("category", "")).strip()
        }
        low_confidence_categories = [
            category for category, score in category_confidence_map.items() if score < 0.5
        ]

        systemic_weakness_detected = (
            len(categories) >= 3
            and (distribution.get("high", 0) + distribution.get("critical", 0)) > 0
        )
        requires_manual_review = bool(low_confidence_categories) or distribution.get("critical", 0) > 0

        external_report["security_posture"] = {
            "attack_surface_vector": categories,
            "risk_distribution": distribution,
            "category_confidence_map": category_confidence_map,
            "systemic_weakness_detected": systemic_weakness_detected,
            "requires_manual_review": requires_manual_review,
        }

        log_agent(state["scan_id"], "Layer11", "Security posture constructed")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer11", f"Security posture build failed: {exc}")

    return merge_state(state, {"external_report": external_report})


async def export_formats_preparer_node(state: ScanState) -> ScanState:
    external_exports = dict(state.get("external_exports", {}))
    external_report = dict(state.get("external_report", {}))

    try:
        executive_summary = dict(external_report.get("executive_summary", {}))
        security_posture = dict(external_report.get("security_posture", {}))

        json_export_object = {
            "scan_id": state["scan_id"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": executive_summary,
            "security_posture": security_posture,
            "telemetry": dict(state.get("telemetry", {})),
            "audit_record": dict(state.get("audit_record", {})),
        }

        markdown_report = (
            f"# deplAI Security Summary\\n\\n"
            f"- Scan ID: {state['scan_id']}\\n"
            f"- Risk Level: {executive_summary.get('risk_level', 'low')}\\n"
            f"- Total Findings: {executive_summary.get('total_findings', 0)}\\n"
            f"- Critical Findings: {executive_summary.get('critical_findings', 0)}\\n"
            f"- Primary Risk Area: {executive_summary.get('primary_risk_area', 'none')}\\n"
            f"- Recommended Action: {executive_summary.get('recommended_next_action', 'maintain_baseline_monitoring')}\\n"
        )

        compact_summary_blob = {
            "scan_id": state["scan_id"],
            "risk_level": executive_summary.get("risk_level", "low"),
            "critical": executive_summary.get("critical_findings", 0),
            "total": executive_summary.get("total_findings", 0),
            "manual_review": security_posture.get("requires_manual_review", False),
            "categories": executive_summary.get("owasp_categories", []),
        }

        external_exports.update(
            {
                "json_export": json_export_object,
                "markdown_report": markdown_report,
                "compact_summary_blob": compact_summary_blob,
                "hook_stubs": {
                    "slack_webhook": "available",
                    "jira_ticket": "available",
                    "github_security_alert": "available",
                    "email_notifier": "available",
                },
            }
        )

        _slack_webhook_stub(json_export_object, enabled=False)
        _jira_ticket_creation_stub(json_export_object, enabled=False)
        _github_security_alert_stub(json_export_object, enabled=False)
        _email_notifier_stub(json_export_object, enabled=False)

        log_agent(state["scan_id"], "Layer11", "Exports prepared")
    except Exception as exc:  # noqa: BLE001
        log_agent(state["scan_id"], "Layer11", f"Export preparation failed: {exc}")

    return merge_state(state, {"external_exports": external_exports})
