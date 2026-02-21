from pydantic import BaseModel
from typing import Optional
from typing import Any


class ScanValidationRequest(BaseModel):
    project_id: str
    project_name: str
    project_type: str
    user_id: str
    deployment_url: Optional[str] = None
    # GitHub-specific fields (only for github projects)
    github_token: Optional[str] = None
    repository_url: Optional[str] = None


class ScanValidationResponseData(BaseModel):
    project_id: str
    project_name: str
    project_type: str
    user_id: str
    deployment_url: Optional[str] = None
    repository_url: Optional[str] = None


class ScanValidationResponse(BaseModel):
    success: bool
    message: str
    data: ScanValidationResponseData
    scan_id: Optional[str] = None
    status: Optional[str] = None


class ScanRequest(BaseModel):
    repo_url: str
    github_token: Optional[str] = None


class ScanResponse(BaseModel):
    scan_id: str
    repo_url: str
    repo_path: Optional[str]
    repo_metadata: dict[str, Any]
    docker_volumes: dict[str, str]
    requires_hitl: bool
    errors: list[str]
    phase: str
    findings: list[dict[str, Any]] = []
    normalized_findings: list[dict[str, Any]] = []
    raw_tool_outputs: list[dict[str, Any]] = []
    owasp_mapped: dict[str, list[dict[str, Any]]] = {}
    owasp_categories: list[str] = []
    coverage_gaps: list[str] = []
    rescans_triggered: bool = False
    setup_phase: str = "not_started"
    analysis_phase: str = "not_started"
    analysis_stage: str = "not_started"
    base_scores: dict[str, float] = {}
    correlated_scores: dict[str, float] = {}
    selected_owasp_categories: list[str] = []
    filtered_categories: list[str] = []
    execution_plan: list[dict[str, Any]] = []
    correlation_phase: str = "not_started"
    correlation_stage: str = "not_started"
    layer6_results: list[dict[str, Any]] = []
    final_findings: list[dict[str, Any]] = []
    execution_phase: str = "not_started"
    execution_stage: str = "not_started"
    artifact_catalog: list[dict[str, Any]] = []
    unified_findings: list[dict[str, Any]] = []
    dedup_clusters: list[dict[str, Any]] = []
    intelligent_findings: list[dict[str, Any]] = []
    dedup_phase: str = "not_started"
    cleanup_status: dict[str, Any] = {
        "persistence_completed": False,
        "persisted_count": 0,
        "volume_removed": False,
        "completed": False,
    }
    telemetry: dict[str, Any] = {
        "scan_summary": {},
        "intelligence_summary": {},
    }
    audit_record: dict[str, Any] = {}
    external_report: dict[str, Any] = {
        "executive_summary": {},
        "security_posture": {},
    }
    external_exports: dict[str, Any] = {
        "json_export": {},
        "markdown_report": "",
        "compact_summary_blob": {},
    }
    phase_timeline: list[dict[str, str]] = []
