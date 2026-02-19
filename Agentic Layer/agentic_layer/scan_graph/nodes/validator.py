from __future__ import annotations

from urllib.parse import urlparse

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def request_validator_node(state: ScanState) -> ScanState:
    # A node is a unit of work in StateGraph.
    # This validator checks repository URL shape and basic scan prerequisites.
    log_agent(state["scan_id"], "RequestValidator", "Starting request validation")
    parsed = urlparse(state["repo_url"])
    is_repo_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    errors = list(state["errors"])
    repo_metadata = dict(state["repo_metadata"])

    if not is_repo_url:
        errors.append("Repository URL is invalid")

    has_permission = "github.com" in state["repo_url"]
    if not has_permission:
        errors.append("User does not have permission for this repository source")

    prerequisites_ok = is_repo_url and has_permission

    repo_metadata["validation"] = {
        "repo_url_valid": is_repo_url,
        "has_permission": has_permission,
        "prerequisites_ok": prerequisites_ok,
    }

    log_agent(
        state["scan_id"],
        "RequestValidator",
        f"Validation complete: url_valid={is_repo_url}, permission={has_permission}, errors={len(errors)}",
    )

    return merge_state(
        state,
        {
            "phase": "validation",
            "errors": errors,
            "repo_metadata": repo_metadata,
        },
    )


def route_after_validation(state: ScanState) -> str:
    # Conditional edges use this router to choose next node path.
    if state["errors"]:
        log_agent(state["scan_id"], "RequestValidator", "Routing to error handler")
        return "error"
    log_agent(state["scan_id"], "RequestValidator", "Routing to GitHub auth")
    return "ok"
