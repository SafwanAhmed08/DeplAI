from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
import inspect
import os
from typing import Any
from typing import Callable

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


_ALLOWED_DECISIONS = {"approve", "reject"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_decision(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if value in {"approve", "approved", "continue", "proceed"}:
        return "approve"
    if value in {"reject", "denied", "cancel", "stop"}:
        return "reject"
    return None


def _resolve_timeout_seconds(state: ScanState, config: dict[str, Any] | None) -> int:
    configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    timeout_from_config = configurable.get("hitl_timeout_seconds") if isinstance(configurable, dict) else None
    if isinstance(timeout_from_config, int) and timeout_from_config > 0:
        return timeout_from_config

    timeout_from_env = os.getenv("DEPLAI_HITL_TIMEOUT_SECONDS")
    if timeout_from_env and timeout_from_env.isdigit() and int(timeout_from_env) > 0:
        return int(timeout_from_env)

    existing = state.get("repo_metadata", {}).get("hitl", {}).get("timeout_seconds")
    if isinstance(existing, int) and existing > 0:
        return existing

    return 60


def _resolve_default_decision(state: ScanState, config: dict[str, Any] | None) -> str:
    configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    default_from_config = configurable.get("hitl_default_decision") if isinstance(configurable, dict) else None
    normalized_from_config = _normalize_decision(default_from_config)
    if normalized_from_config:
        return normalized_from_config

    default_from_env = _normalize_decision(os.getenv("DEPLAI_HITL_DEFAULT_DECISION"))
    if default_from_env:
        return default_from_env

    existing = _normalize_decision(state.get("repo_metadata", {}).get("hitl", {}).get("default_decision"))
    if existing:
        return existing

    return "reject"


async def _get_provider_decision(
    scan_id: str,
    provider: Callable[[str], Any],
) -> dict[str, Any] | None:
    response = provider(scan_id)
    if inspect.isawaitable(response):
        response = await response

    if isinstance(response, dict):
        decision = _normalize_decision(response.get("decision"))
        if decision:
            return {
                "decision": decision,
                "source": str(response.get("source") or "user"),
                "actor": str(response.get("actor") or "unknown"),
                "reason": str(response.get("reason") or ""),
            }
        return None

    normalized = _normalize_decision(response)
    if normalized:
        return {
            "decision": normalized,
            "source": "user",
            "actor": "unknown",
            "reason": "",
        }

    return None


def _state_embedded_decision(state: ScanState) -> dict[str, Any] | None:
    hitl = state.get("repo_metadata", {}).get("hitl", {})
    decision = _normalize_decision(hitl.get("decision"))
    if not decision:
        return None
    return {
        "decision": decision,
        "source": str(hitl.get("decision_source") or "state"),
        "actor": str(hitl.get("decision_actor") or "unknown"),
        "reason": str(hitl.get("decision_reason") or ""),
    }


async def hitl_prompt_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    timeout_seconds = _resolve_timeout_seconds(state, config)
    default_decision = _resolve_default_decision(state, config)

    hitl_metadata = {
        **state.get("repo_metadata", {}).get("hitl", {}),
        "status": "awaiting_decision",
        "requested_at": _utc_now_iso(),
        "timeout_seconds": timeout_seconds,
        "default_decision": default_decision,
        "question": "Repository size exceeds threshold. Approve full scan?",
        "options": ["approve", "reject"],
    }

    log_agent(
        state["scan_id"],
        "HITLAgent",
        f"Decision requested timeout={timeout_seconds}s default={default_decision}",
    )

    return merge_state(
        state,
        {
            "phase": "hitl_waiting",
            "hitl_phase": "awaiting_decision",
            "repo_metadata": {
                **state["repo_metadata"],
                "hitl": hitl_metadata,
            },
        },
    )


async def hitl_wait_for_decision_node(state: ScanState, config: dict[str, Any] | None = None) -> ScanState:
    hitl = dict(state.get("repo_metadata", {}).get("hitl", {}))
    timeout_seconds = int(hitl.get("timeout_seconds") or 60)
    default_decision = _normalize_decision(hitl.get("default_decision")) or "reject"
    poll_seconds = 2

    configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    provider = configurable.get("hitl_decision_provider") if isinstance(configurable, dict) else None

    started = asyncio.get_running_loop().time()
    resolved: dict[str, Any] | None = _state_embedded_decision(state)

    while resolved is None and (asyncio.get_running_loop().time() - started) < timeout_seconds:
        if callable(provider):
            try:
                resolved = await _get_provider_decision(state["scan_id"], provider)
            except Exception as exc:  # noqa: BLE001
                log_agent(state["scan_id"], "HITLAgent", f"Decision provider failed: {exc}")
        if resolved is not None:
            break
        await asyncio.sleep(poll_seconds)

    timed_out = resolved is None
    if timed_out:
        resolved = {
            "decision": default_decision,
            "source": "timeout_default",
            "actor": "system",
            "reason": "No user decision received before timeout",
        }

    decision = str(resolved.get("decision") or "reject")
    if decision not in _ALLOWED_DECISIONS:
        decision = default_decision

    hitl.update(
        {
            "status": "decision_resolved",
            "decided_at": _utc_now_iso(),
            "decision": decision,
            "decision_source": str(resolved.get("source") or "unknown"),
            "decision_actor": str(resolved.get("actor") or "unknown"),
            "decision_reason": str(resolved.get("reason") or ""),
            "timed_out": timed_out,
        }
    )

    log_agent(
        state["scan_id"],
        "HITLAgent",
        f"Decision resolved decision={decision} source={hitl['decision_source']} timed_out={timed_out}",
    )

    return merge_state(
        state,
        {
            "phase": "hitl_resolved",
            "hitl_phase": "decision_resolved",
            "repo_metadata": {
                **state["repo_metadata"],
                "hitl": hitl,
            },
        },
    )


async def hitl_apply_decision_node(state: ScanState) -> ScanState:
    hitl = dict(state.get("repo_metadata", {}).get("hitl", {}))
    decision = _normalize_decision(hitl.get("decision")) or "reject"

    updates: dict[str, Any] = {
        "requires_hitl": False,
        "hitl_phase": "completed",
    }

    if decision == "reject":
        updates.update(
            {
                "analysis_phase": "skipped",
                "correlation_phase": "skipped",
                "execution_phase": "skipped",
                "analysis_stage": "skipped_due_to_hitl_rejection",
                "correlation_stage": "skipped_due_to_hitl_rejection",
                "execution_stage": "skipped_due_to_hitl_rejection",
            }
        )
        log_agent(state["scan_id"], "HITLAgent", "Decision rejected: analysis pipeline skipped")
    else:
        log_agent(state["scan_id"], "HITLAgent", "Decision approved: analysis pipeline resumes")

    return merge_state(state, updates)
