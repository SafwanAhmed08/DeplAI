from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.graph import execute_scan_workflow
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import build_initial_state
from agentic_layer.scan_graph.state import merge_state


def _sanitize_state_for_response(state: ScanState) -> dict[str, Any]:
    safe_state = dict(state)
    safe_state.pop("github_token", None)
    return safe_state


class StartScanRequest(BaseModel):
    repo_url: str = Field(..., examples=["https://github.com/org/repo"])
    project_id: str = Field(..., examples=["project-123"])
    github_token: str | None = None


class StartScanResponse(BaseModel):
    scan_id: str
    status: str


class ScanStatusResponse(BaseModel):
    status: str
    current_phase: str
    messages: list[str]
    errors: list[str]


class ScanResultsResponse(BaseModel):
    scan_id: str
    status: str
    state: dict[str, Any]


class HitlDecisionRequest(BaseModel):
    decision: str = Field(..., examples=["approve", "reject"])
    actor: str | None = Field(default=None, examples=["user-123"])
    reason: str | None = Field(default=None, examples=["Repo is trusted and scan should continue"])


class HitlDecisionResponse(BaseModel):
    scan_id: str
    accepted: bool
    decision: str


class ScanService:
    def __init__(self) -> None:
        self._registry: dict[str, ScanState] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._ephemeral_tokens: dict[str, str] = {}
        self._hitl_decisions: dict[str, dict[str, str]] = {}
        self._lock = asyncio.Lock()

    async def start_scan(self, repo_url: str, project_id: str, github_token: str | None = None) -> str:
        initial_state = build_initial_state(repo_url=repo_url)
        started_state = merge_state(
            initial_state,
            {
                "phase": "started",
                "repo_metadata": {
                    **initial_state["repo_metadata"],
                    "project": {"project_id": project_id},
                },
            },
        )
        scan_id = started_state["scan_id"]
        log_agent(scan_id, "ScanService", f"Scan accepted for project_id={project_id}")
        log_agent(scan_id, "ScanService", f"Token received at start_scan={bool(github_token and github_token.strip())}")

        async with self._lock:
            self._registry[scan_id] = started_state
            if github_token and github_token.strip():
                self._ephemeral_tokens[scan_id] = github_token.strip()
            self._tasks[scan_id] = asyncio.create_task(self._run_scan(scan_id))

        return scan_id

    async def _run_scan(self, scan_id: str) -> None:
        state = await self.get_scan_state(scan_id)
        if state is None:
            return
        log_agent(scan_id, "ScanService", "Background scan task started")

        running_state = merge_state(state, {"phase": "running"})
        await self._set_scan_state(scan_id, running_state)

        messages = ["Scan started", "Validation and setup running"]
        running_state = merge_state(
            running_state,
            {
                "repo_metadata": {
                    **running_state["repo_metadata"],
                    "messages": messages,
                }
            },
        )
        await self._set_scan_state(scan_id, running_state)
        log_agent(scan_id, "ScanService", "Scan state marked as running")

        try:
            github_token = None
            async with self._lock:
                github_token = self._ephemeral_tokens.pop(scan_id, None)

            invoke_state = merge_state(running_state, {"github_token": github_token})
            log_agent(scan_id, "ScanService", f"Token injected into state before invoke={bool(github_token)}")

            final_state = await execute_scan_workflow(
                invoke_state,
                config={
                    "configurable": {
                        "github_token": github_token,
                        "hitl_decision_provider": self.get_hitl_decision,
                    }
                },
            )
            final_state = merge_state(
                final_state,
                {
                    "repo_metadata": {
                        **final_state["repo_metadata"],
                        "messages": [*messages, "Scan completed"],
                    }
                },
            )
            await self._set_scan_state(scan_id, final_state)
            log_agent(scan_id, "ScanService", f"Background scan finished at phase={final_state['phase']}")
        except Exception:
            failed_state = merge_state(
                running_state,
                {
                    "phase": "error",
                    "errors": [*running_state["errors"], "Scan execution failed"],
                    "repo_metadata": {
                        **running_state["repo_metadata"],
                        "messages": [*messages, "Scan failed"],
                    },
                },
            )
            await self._set_scan_state(scan_id, failed_state)
            log_agent(scan_id, "ScanService", "Background scan failed")
        finally:
            async with self._lock:
                self._tasks.pop(scan_id, None)
                self._ephemeral_tokens.pop(scan_id, None)
                self._hitl_decisions.pop(scan_id, None)
            log_agent(scan_id, "ScanService", "Background task cleaned up")

    def get_hitl_decision(self, scan_id: str) -> dict[str, str] | None:
        return self._hitl_decisions.get(scan_id)

    async def submit_hitl_decision(
        self,
        scan_id: str,
        decision: str,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            return False

        async with self._lock:
            if scan_id not in self._registry:
                return False

            self._hitl_decisions[scan_id] = {
                "decision": normalized,
                "source": "user",
                "actor": (actor or "unknown").strip() or "unknown",
                "reason": (reason or "").strip(),
            }

            current_state = self._registry[scan_id]
            hitl_meta = {
                **current_state.get("repo_metadata", {}).get("hitl", {}),
                "decision": normalized,
                "decision_source": "user",
                "decision_actor": (actor or "unknown").strip() or "unknown",
                "decision_reason": (reason or "").strip(),
            }
            updated_state = merge_state(
                current_state,
                {
                    "repo_metadata": {
                        **current_state["repo_metadata"],
                        "hitl": hitl_meta,
                    }
                },
            )
            self._registry[scan_id] = updated_state

        log_agent(scan_id, "ScanService", f"HITL decision submitted decision={normalized}")
        return True

    async def get_scan_state(self, scan_id: str) -> ScanState | None:
        async with self._lock:
            state = self._registry.get(scan_id)
            return None if state is None else merge_state(state, {})

    async def _set_scan_state(self, scan_id: str, state: ScanState) -> None:
        async with self._lock:
            self._registry[scan_id] = merge_state(state, {})

    async def get_status_view(self, scan_id: str) -> dict[str, Any] | None:
        state = await self.get_scan_state(scan_id)
        if state is None:
            return None

        messages = state["repo_metadata"].get("messages", [])
        status = "completed"
        if state["phase"] in {"started", "running"}:
            status = "running"
        if state["phase"] == "error" or state["errors"]:
            status = "failed"

        return {
            "status": status,
            "current_phase": state["phase"],
            "messages": messages,
            "errors": state["errors"],
        }

    async def get_results_view(self, scan_id: str) -> dict[str, Any] | None:
        state = await self.get_scan_state(scan_id)
        if state is None:
            return None

        status = "completed"
        if state["phase"] in {"started", "running"}:
            status = "running"
        if state["phase"] == "error" or state["errors"]:
            status = "failed"

        return {
            "scan_id": state["scan_id"],
            "status": status,
            "state": _sanitize_state_for_response(state),
        }


scan_service = ScanService()
scan_router = APIRouter(tags=["scan"])


@scan_router.post("/scan/start", response_model=StartScanResponse)
async def start_scan(payload: StartScanRequest) -> StartScanResponse:
    try:
        scan_id = await scan_service.start_scan(
            repo_url=payload.repo_url,
            project_id=payload.project_id,
            github_token=payload.github_token,
        )
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Unable to start scan")

    log_agent(scan_id, "ScanAPI", "POST /scan/start responded with started status")

    return StartScanResponse(scan_id=scan_id, status="started")


@scan_router.get("/scan/{scan_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(scan_id: str) -> ScanStatusResponse:
    status_view = await scan_service.get_status_view(scan_id)
    if status_view is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    log_agent(scan_id, "ScanAPI", f"GET /scan/{scan_id}/status -> {status_view['status']}")

    return ScanStatusResponse(**status_view)


@scan_router.get("/scan/{scan_id}/results", response_model=ScanResultsResponse)
async def get_scan_results(scan_id: str) -> ScanResultsResponse:
    results_view = await scan_service.get_results_view(scan_id)
    if results_view is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    log_agent(scan_id, "ScanAPI", f"GET /scan/{scan_id}/results -> {results_view['status']}")

    return ScanResultsResponse(**results_view)


@scan_router.post("/scan/{scan_id}/hitl-decision", response_model=HitlDecisionResponse)
async def submit_hitl_decision(scan_id: str, payload: HitlDecisionRequest) -> HitlDecisionResponse:
    accepted = await scan_service.submit_hitl_decision(
        scan_id=scan_id,
        decision=payload.decision,
        actor=payload.actor,
        reason=payload.reason,
    )
    if not accepted:
        raise HTTPException(status_code=400, detail="Invalid decision or scan not found")

    log_agent(scan_id, "ScanAPI", f"POST /scan/{scan_id}/hitl-decision accepted")
    return HitlDecisionResponse(scan_id=scan_id, accepted=True, decision=payload.decision.strip().lower())
