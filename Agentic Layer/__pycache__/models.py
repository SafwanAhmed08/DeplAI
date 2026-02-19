from pydantic import BaseModel
from typing import Optional


class ScanValidationRequest(BaseModel):
    project_id: str
    project_name: str
    project_type: str
    user_id: str
    deployment_url: Optional[str] = None
    # GitHub-specific fields (only for github projects)
    github_token: Optional[str] = None
    repository_url: Optional[str] = None


class ScanValidationResponse(BaseModel):
    success: bool
    message: str
    data: ScanValidationRequest
