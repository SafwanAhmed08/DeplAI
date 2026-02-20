from __future__ import annotations

from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


async def analysis_planner_node(state: ScanState) -> ScanState:
    # Planner decides what scanners to run based on repo characteristics.
    log_agent(state["scan_id"], "AnalysisPlanner", "Planning analysis scanner execution")

    repo_path = state["repo_path"] or ""
    path = Path(repo_path) if repo_path else None

    has_python = False
    has_requirements = False
    has_config_files = False

    if path and path.exists():
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            name = file_path.name.lower()
            if file_path.suffix.lower() == ".py":
                has_python = True
            if name in {"requirements.txt", "pyproject.toml", "poetry.lock"}:
                has_requirements = True
            if name in {".env", "config.yml", "config.yaml", "settings.json"}:
                has_config_files = True

    repo_metadata = dict(state["repo_metadata"])
    repo_metadata["analysis_plan"] = {
        "run_ast_scanner": has_python,
        "run_regex_scanner": True,
        "run_dependency_scanner": has_requirements,
        "run_config_scanner": has_config_files,
    }

    return merge_state(
        state,
        {
            "phase": "analysis",
            "analysis_stage": "planned",
            "repo_metadata": repo_metadata,
        },
    )
