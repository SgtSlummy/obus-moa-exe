"""Create inspect-only, redacted evidence from one durable OBus task."""
from __future__ import annotations

from typing import Any

from backend.secret_safety import redact_text


def task_evidence(task: dict[str, Any]) -> dict[str, Any]:
    """Return comparison evidence without replaying a task or claiming a score."""
    return {
        "schema_version": 1,
        "product": "obus",
        "kind": "task-evidence",
        "task": {
            "id": str(task.get("id") or ""),
            "state": str(task.get("state") or "unknown"),
            "provider": str(task.get("provider") or "unknown"),
            "attempt": int(task.get("attempt") or 0),
            "max_attempts": int(task.get("max_attempts") or 0),
            "started_at": str(task.get("started_at") or ""),
            "finished_at": str(task.get("finished_at") or ""),
        },
        "evidence": {
            "objective_preview": redact_text(task.get("objective"), 1200),
            "result_preview": redact_text(task.get("result"), 4000),
            "error_preview": redact_text(task.get("error"), 1200),
        },
        "verifier": {"required": True, "score": None, "notice": "This export is evidence only. A human verifier must assign a fixture score."},
        "replay": "none",
    }
