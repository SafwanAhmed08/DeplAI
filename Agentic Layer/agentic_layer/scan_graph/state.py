from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any
from typing import TypedDict
from uuid import uuid4

from agentic_layer.scan_graph.logger import log_agent


class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SecurityError(RuntimeError):
    pass


class CleanupStatus(TypedDict):
    persistence_completed: bool
    persisted_count: int
    volume_removed: bool
    completed: bool


class ScanState(TypedDict):
    # Core identity and source information.
    scan_id: str
    repo_url: str
    repo_path: str | None
    github_token: str | None

    # Collected setup data.
    repo_metadata: dict[str, Any]
    docker_volumes: dict[str, str]

    # Routing and status.
    requires_hitl: bool
    errors: list[str]
    phase: str

    # Analysis phase fields.
    setup_phase: str
    hitl_phase: str
    findings: list[dict[str, Any]]
    raw_tool_outputs: list[dict[str, Any]]
    owasp_mapped: dict[str, list[dict[str, Any]]]
    coverage_gaps: list[str]
    rescans_triggered: bool
    analysis_phase: str
    analysis_stage: str
    base_scores: dict[str, float]
    correlated_scores: dict[str, float]
    selected_owasp_categories: list[str]
    filtered_categories: list[str]
    execution_plan: list[dict[str, Any]]
    correlation_phase: str
    correlation_stage: str
    normalized_findings: list[dict[str, Any]]
    owasp_categories: list[str]
    layer6_results: list[dict[str, Any]]
    final_findings: list[dict[str, Any]]
    execution_phase: str
    execution_stage: str
    artifact_catalog: list[dict[str, Any]]
    unified_findings: list[dict[str, Any]]
    dedup_clusters: list[dict[str, Any]]
    intelligent_findings: list[dict[str, Any]]
    dedup_phase: str
    cleanup_status: CleanupStatus
    telemetry: dict[str, Any]
    audit_record: dict[str, Any]
    external_report: dict[str, Any]
    external_exports: dict[str, Any]
    phase_timeline: list[dict[str, str]]


def _ensure_no_secret_state_keys(state_like: dict[str, Any]) -> None:
    allowed_secret_like_keys = {"github_token"}
    forbidden_keys = [
        key
        for key in state_like.keys()
        if ("token" in key.lower() or "key" in key.lower()) and key not in allowed_secret_like_keys
    ]
    if forbidden_keys:
        raise SecurityError(f"Forbidden secret-like key(s) in state: {', '.join(sorted(forbidden_keys))}")


def merge_state(old_state: ScanState, updates: dict[str, Any]) -> ScanState:
    # LangGraph nodes should treat state as immutable snapshots.
    # We deep-copy to avoid in-place mutation bugs between nodes.
    allowed_secret_like_keys = {"github_token"}
    next_state = deepcopy(old_state)
    for key, value in updates.items():
        if ("token" in key.lower() or "key" in key.lower()) and key not in allowed_secret_like_keys:
            raise SecurityError(f"Forbidden secret-like key in state update: {key}")
        next_state[key] = value
    _ensure_no_secret_state_keys(next_state)
    log_agent(next_state["scan_id"], "SecurityGuard", "Secret persistence check passed")
    return next_state


def build_initial_state(repo_url: str) -> ScanState:
    # Initial state is minimal and expanded by nodes over time.
    now = datetime.now(timezone.utc).isoformat()
    initial_state: ScanState = {
        "scan_id": str(uuid4()),
        "repo_url": repo_url,
        "repo_path": None,
        "github_token": None,
        "repo_metadata": {},
        "docker_volumes": {},
        "requires_hitl": False,
        "errors": [],
        "phase": "master_orchestrator",
        "setup_phase": PhaseStatus.NOT_STARTED.value,
        "hitl_phase": PhaseStatus.NOT_STARTED.value,
        "findings": [],
        "raw_tool_outputs": [],
        "owasp_mapped": {},
        "coverage_gaps": [],
        "rescans_triggered": False,
        "analysis_phase": PhaseStatus.NOT_STARTED.value,
        "analysis_stage": "not_started",
        "base_scores": {},
        "correlated_scores": {},
        "selected_owasp_categories": [],
        "filtered_categories": [],
        "execution_plan": [],
        "correlation_phase": PhaseStatus.NOT_STARTED.value,
        "correlation_stage": "not_started",
        "normalized_findings": [],
        "owasp_categories": [],
        "layer6_results": [],
        "final_findings": [],
        "execution_phase": PhaseStatus.NOT_STARTED.value,
        "execution_stage": "not_started",
        "artifact_catalog": [],
        "unified_findings": [],
        "dedup_clusters": [],
        "intelligent_findings": [],
        "dedup_phase": PhaseStatus.NOT_STARTED.value,
        "cleanup_status": {
            "persistence_completed": False,
            "persisted_count": 0,
            "volume_removed": False,
            "completed": False,
        },
        "telemetry": {
            "scan_summary": {},
            "intelligence_summary": {},
        },
        "audit_record": {},
        "external_report": {
            "executive_summary": {},
            "security_posture": {},
        },
        "external_exports": {
            "json_export": {},
            "markdown_report": "",
            "compact_summary_blob": {},
        },
        "phase_timeline": [
            {
                "phase": "master_orchestrator",
                "event": "initialized",
                "at": now,
            }
        ],
    }
    _ensure_no_secret_state_keys(initial_state)
    log_agent(initial_state["scan_id"], "SecurityGuard", "Secret persistence check passed")
    return initial_state


def append_timeline_event(state: ScanState, phase: str, event: str) -> ScanState:
    entry = {
        "phase": phase,
        "event": event,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    return merge_state(state, {"phase_timeline": [*state["phase_timeline"], entry]})
