from __future__ import annotations

from pathlib import Path

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".js": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}


async def codebase_stats_node(state: ScanState) -> ScanState:
    # Computes file counts, total size, and language breakdown.
    log_agent(state["scan_id"], "CodebaseStats", "Computing codebase statistics")
    repo_path = state["repo_path"]
    repo_metadata = dict(state["repo_metadata"])

    if repo_path is None:
        log_agent(state["scan_id"], "CodebaseStats", "Repository path missing, stats failed")
        return merge_state(
            state,
            {
                "phase": "stats_failed",
                "errors": [*state["errors"], "Repository path missing for stats"],
            },
        )

    path = Path(repo_path)
    total_files = 0
    total_size_bytes = 0
    language_breakdown: dict[str, int] = {}

    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        total_files += 1
        total_size_bytes += file_path.stat().st_size

        language = LANGUAGE_EXTENSIONS.get(file_path.suffix.lower(), "other")
        language_breakdown[language] = language_breakdown.get(language, 0) + 1

    repo_metadata["stats"] = {
        "total_files": total_files,
        "total_size_bytes": total_size_bytes,
        "language_breakdown": language_breakdown,
    }
    log_agent(
        state["scan_id"],
        "CodebaseStats",
        f"Stats complete: files={total_files}, size_bytes={total_size_bytes}",
    )

    return merge_state(
        state,
        {
            "phase": "stats_computed",
            "repo_metadata": repo_metadata,
        },
    )
