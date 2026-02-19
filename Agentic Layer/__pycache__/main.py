from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ScanValidationRequest, ScanValidationResponse

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
        if request.github_token:
            print(f"GitHub Token:    {request.github_token[:20]}..." if len(request.github_token) > 20 else f"GitHub Token:    {request.github_token}")

    # Only show deployment URL if provided
    if request.deployment_url:
        print(f"Deployment URL:  {request.deployment_url}")

    print("=" * 50 + "\n")

    return ScanValidationResponse(
        success=True,
        message="Scan validation request received successfully",
        data=request
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
