from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models import ScanRequest
from models import ScanResponse
from models import ScanValidationRequest
from models import ScanValidationResponseData
from models import ScanValidationResponse

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.graph import execute_scan_workflow
from agentic_layer.scan_graph.state import build_initial_state
from scan_router import scan_router
from scan_router import scan_service

app = FastAPI(
    title="DEPLAI Agentic Layer",
    description="Backend API for scan validation",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/scan/validate", response_model=ScanValidationResponse)
async def validate_scan(request: ScanValidationRequest):
    """
    Validate a scan request from the frontend.

    Required fields:
    - project_id: The project identifier
    - project_type: The type of project
    - user_id: The user identifier

    Optional fields:
    - deployment_url: The deployment URL (if available)
    """
    # Print request details to terminal
    print("\n" + "=" * 50)
    print("SCAN VALIDATION REQUEST RECEIVED")
    print("=" * 50)
    print(f"Project ID:      {request.project_id}")
    print(f"Project Name:    {request.project_name}")
    print(f"Project Type:    {request.project_type}")
    print(f"User ID:         {request.user_id}")

    # Only show GitHub-specific fields for github projects
    if request.project_type == "github":
        if request.repository_url:
            print(f"Repository URL:  {request.repository_url}")

    # Only show deployment URL if provided
    if request.deployment_url:
        print(f"Deployment URL:  {request.deployment_url}")

    print("=" * 50 + "\n")

    # Trigger LangGraph lifecycle after validation success.
    # This is non-blocking because scan_service schedules the workflow with asyncio.create_task.
    try:
        repo_url = request.repository_url or ""
        if not repo_url:
            raise HTTPException(status_code=400, detail="repository_url is required for scan start")

        scan_id = await scan_service.start_scan(
            repo_url=repo_url,
            project_id=request.project_id,
            github_token=request.github_token,
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to start scan")

    log_agent(scan_id, "ValidationAPI", "Validation completed and background scan started")

    return ScanValidationResponse(
        success=True,
        message="Scan validation request received and scan started",
        data=ScanValidationResponseData(
            project_id=request.project_id,
            project_name=request.project_name,
            project_type=request.project_type,
            user_id=request.user_id,
            deployment_url=request.deployment_url,
            repository_url=request.repository_url,
        ),
        scan_id=scan_id,
        status="started",
    )


@app.post("/scan", response_model=ScanResponse)
async def run_scan(request: ScanRequest):
    # FastAPI endpoint integration:
    # 1) Build initial typed state
    # 2) Invoke master LangGraph orchestrator
    # 3) Return final state snapshot to caller
    #
    # This demonstrates how existing backend API calls into graph orchestration
    # without redesigning the rest of the backend.
    initial_state = build_initial_state(
        repo_url=request.repo_url,
        github_token=request.github_token,
    )

    final_state = await execute_scan_workflow(initial_state)

    return ScanResponse(
        scan_id=final_state["scan_id"],
        repo_url=final_state["repo_url"],
        repo_path=final_state["repo_path"],
        repo_metadata=final_state["repo_metadata"],
        docker_volumes=final_state["docker_volumes"],
        requires_hitl=final_state["requires_hitl"],
        errors=final_state["errors"],
        phase=final_state["phase"],
        findings=final_state["findings"],
        raw_tool_outputs=final_state["raw_tool_outputs"],
        owasp_mapped=final_state["owasp_mapped"],
        coverage_gaps=final_state["coverage_gaps"],
        rescans_triggered=final_state["rescans_triggered"],
        analysis_phase=final_state["analysis_phase"],
        base_scores=final_state["base_scores"],
        correlated_scores=final_state["correlated_scores"],
        selected_owasp_categories=final_state["selected_owasp_categories"],
        filtered_categories=final_state["filtered_categories"],
        execution_plan=final_state["execution_plan"],
        correlation_phase=final_state["correlation_phase"],
        phase_timeline=final_state["phase_timeline"],
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


app.include_router(scan_router)
