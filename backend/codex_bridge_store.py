"""Durable, secret-free metadata for explicitly created OBus Codex threads."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


MAX_THREADS = 50


def default_store_path() -> Path:
    root = Path(
        os.environ.get("OBUS_STATE_DIR")
        or os.environ.get("OCCULTBUS_HOME")
        or Path.home() / ".occultbus"
    )
    return root / "codex_bridge_threads.json"


class CodexBridgeThreadStore:
    """Persist only thread identifiers and their selected workspace binding.

    Codex keeps the conversation itself in its own rollout store.  OBus stores
    no prompts, events, provider credentials, or approval decisions here.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        rows = value.get("threads") if isinstance(value, dict) else None
        if not isinstance(rows, list):
            return []
        result: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            thread_id, workspace = row.get("thread_id"), row.get("workspace")
            if not isinstance(thread_id, str) or not thread_id.strip() or not isinstance(workspace, str) or not workspace.strip():
                continue
            result.append(
                {
                    "thread_id": thread_id[:256],
                    "workspace": workspace[:1000],
                    "model": row.get("model")[:160] if isinstance(row.get("model"), str) else None,
                    "updated_at": float(row.get("updated_at") or 0),
                }
            )
        return result

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "threads": rows[:MAX_THREADS]}, separators=(",", ":"))
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=self.path.parent, prefix=".codex-bridge-", suffix=".tmp"
        ) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def remember(self, thread_id: str, workspace: Path, model: str | None = None) -> dict[str, Any]:
        record = {
            "thread_id": str(thread_id).strip()[:256],
            "workspace": str(workspace.resolve()),
            "model": str(model).strip()[:160] if model else None,
            "updated_at": time.time(),
        }
        if not record["thread_id"]:
            raise ValueError("thread id is required")
        with self._lock:
            rows = [row for row in self._load() if row["thread_id"] != record["thread_id"]]
            rows.insert(0, record)
            self._save(rows)
        return record

    def recent(self, workspace: Path) -> list[dict[str, Any]]:
        selected = str(workspace.resolve()).casefold()
        with self._lock:
            rows = [row for row in self._load() if row["workspace"].casefold() == selected]
        return sorted(rows, key=lambda row: float(row["updated_at"]), reverse=True)[:MAX_THREADS]

    def contains(self, thread_id: str, workspace: Path) -> bool:
        return any(row["thread_id"] == thread_id for row in self.recent(workspace))
