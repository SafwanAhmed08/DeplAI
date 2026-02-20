from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any
from typing import TypedDict
from uuid import uuid4


class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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
    phase_timeline: list[dict[str, str]]


def merge_state(old_state: ScanState, updates: dict[str, Any]) -> ScanState:
    # LangGraph nodes should treat state as immutable snapshots.
    # We deep-copy to avoid in-place mutation bugs between nodes.
    next_state = deepcopy(old_state)
    for key, value in updates.items():
        next_state[key] = value
    return next_state


def build_initial_state(repo_url: str, github_token: str | None = None) -> ScanState:
    # Initial state is minimal and expanded by nodes over time.
    now = datetime.now(timezone.utc).isoformat()
    return {
        "scan_id": str(uuid4()),
        "repo_url": repo_url,
        "repo_path": None,
        "github_token": github_token,
        "repo_metadata": {},
        "docker_volumes": {},
        "requires_hitl": False,
        "errors": [],
        "phase": "master_orchestrator",
        "setup_phase": PhaseStatus.NOT_STARTED.value,
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
        "phase_timeline": [
            {
                "phase": "master_orchestrator",
                "event": "initialized",
                "at": now,
            }
        ],
    }


def append_timeline_event(state: ScanState, phase: str, event: str) -> ScanState:
    entry = {
        "phase": phase,
        "event": event,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    return merge_state(state, {"phase_timeline": [*state["phase_timeline"], entry]})
