from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json
import os
import sqlite3

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _db_path() -> str:
    return os.getenv("DEPLAI_SCAN_DB_PATH", "/tmp/deplai_scans.sqlite3")


def _project_id_from_state(state: ScanState) -> str:
    project_meta = state.get("repo_metadata", {}).get("project", {})
    if isinstance(project_meta, dict):
        project_id = project_meta.get("project_id")
        if isinstance(project_id, str) and project_id.strip():
            return project_id.strip()
    return "unknown"


def _persist_results(state: ScanState) -> int:
    findings = list(state.get("intelligent_findings", []))
    persisted_count = len(findings)
    db_path = _db_path()
    now = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_results (
                scan_id TEXT PRIMARY KEY,
                project_id TEXT,
                status TEXT,
                phase TEXT,
                persisted_count INTEGER,
                findings_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        cursor.execute(
            "SELECT persisted_count FROM scan_results WHERE scan_id = ?",
            (state["scan_id"],),
        )
        row = cursor.fetchone()
        if row is not None:
            return int(row[0] or 0)

        cursor.execute(
            """
            INSERT INTO scan_results (
                scan_id,
                project_id,
                status,
                phase,
                persisted_count,
                findings_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state["scan_id"],
                _project_id_from_state(state),
                "completed",
                str(state.get("phase", "execution_completed")),
                persisted_count,
                json.dumps(findings),
                now,
                now,
            ),
        )
        connection.commit()
        return persisted_count
    finally:
        connection.close()


async def result_persister_node(state: ScanState) -> ScanState:
    cleanup_status = dict(state.get("cleanup_status", {}))
    errors = list(state["errors"])

    if bool(cleanup_status.get("persistence_completed")):
        log_agent(state["scan_id"], "ResultPersister", "Persistence already completed; skipping")
        return merge_state(state, {"cleanup_status": cleanup_status})

    try:
        persisted_count = _persist_results(state)
        cleanup_status["persistence_completed"] = True
        cleanup_status["persisted_count"] = int(persisted_count)
        log_agent(state["scan_id"], "ResultPersister", f"Persisted {persisted_count} findings")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Cleanup persistence failed: {exc}")

    return merge_state(
        state,
        {
            "cleanup_status": cleanup_status,
            "errors": errors,
        },
    )
