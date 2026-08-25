"""Provider discovery and proactive objective scheduling for the Obus harness."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ProviderRegistry:
    """Codex-primary registry with Ollama and OpenAI-compatible local adapters."""

    def __init__(self) -> None:
        self._last_discovery: list[dict[str, Any]] = []

    @staticmethod
    def _probe(url: str, timeout: float = 0.75) -> tuple[bool, dict[str, Any] | list[Any] | None]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return True, payload
        except (OSError, ValueError, urllib.error.URLError):
            return False, None

    def discover(self) -> list[dict[str, Any]]:
        providers: list[dict[str, Any]] = []
        codex_command = os.environ.get("OBUS_CODEX_COMMAND", "codex")
        codex_path = shutil.which(codex_command)
        providers.append({
            "id": "codex", "kind": "codex", "available": bool(codex_path),
            "primary": True, "endpoint": None, "models": [], "detail": codex_path or "command not found",
        })

        ollama_url = os.environ.get("OBUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        available, payload = self._probe(f"{ollama_url}/api/tags")
        models = [item.get("name", "") for item in (payload or {}).get("models", [])] if isinstance(payload, dict) else []
        providers.append({
            "id": "ollama", "kind": "ollama", "available": available,
            "primary": False, "endpoint": ollama_url, "models": [model for model in models if model],
            "detail": "ready" if available else "endpoint unavailable",
        })

        compatible_url = os.environ.get("OBUS_OPENAI_COMPATIBLE_URL", "").rstrip("/")
        if compatible_url:
            available, payload = self._probe(f"{compatible_url}/models")
            data = payload.get("data", []) if isinstance(payload, dict) else []
            models = [item.get("id", "") for item in data if isinstance(item, dict)]
            providers.append({
                "id": "openai-compatible", "kind": "openai-compatible", "available": available,
                "primary": False, "endpoint": compatible_url, "models": [model for model in models if model],
                "detail": "ready" if available else "endpoint unavailable",
            })
        self._last_discovery = providers
        return providers

    def capabilities(self) -> dict[str, Any]:
        providers = self.discover()
        return {"default": "codex", "providers": providers,
                "available": [provider["id"] for provider in providers if provider["available"]]}

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None,
                   timeout: int = 600) -> dict[str, Any]:
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                         headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError("provider returned a non-object response")
        return result

    def run(self, task: dict[str, Any], cancellation: threading.Event,
            emit: Callable[[str, dict[str, Any]], None]) -> str:
        provider = str(task.get("provider") or "codex")
        if provider == "codex":
            return self._run_codex(task, cancellation, emit)
        if provider == "ollama":
            return self._run_ollama(task, cancellation, emit)
        if provider == "openai-compatible":
            return self._run_openai_compatible(task, cancellation, emit)
        raise ValueError(f"unsupported provider: {provider}")

    def _run_codex(self, task: dict[str, Any], cancellation: threading.Event,
                   emit: Callable[[str, dict[str, Any]], None]) -> str:
        command = os.environ.get("OBUS_CODEX_COMMAND", "codex")
        model = os.environ.get("OBUS_CODEX_MODEL", "")
        args = [command, "exec", "--skip-git-repo-check", "--dangerously-bypass-approvals-and-sandbox",
                "--color", "never"]
        if model:
            args.extend(["-m", model])
        args.append(str(task["objective"]))
        emit("provider.started", {"provider": "codex", "model": model or "default"})
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        process = subprocess.Popen(args, cwd=task["workspace"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", creationflags=flags)
        chunks: list[str] = []
        while process.poll() is None:
            if cancellation.wait(0.2):
                process.terminate()
                raise InterruptedError("task cancelled")
        if process.stdout:
            chunks.append(process.stdout.read())
        output = "".join(chunks).strip()
        if process.returncode != 0:
            raise RuntimeError(f"Codex exited with code {process.returncode}: {output[-2000:]}")
        if not output:
            raise RuntimeError("Codex returned no output")
        emit("provider.output", {"provider": "codex", "text": output[-16000:]})
        return output

    def _run_ollama(self, task: dict[str, Any], cancellation: threading.Event,
                    emit: Callable[[str, dict[str, Any]], None]) -> str:
        if cancellation.is_set():
            raise InterruptedError("task cancelled")
        endpoint = os.environ.get("OBUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        model = str(task.get("model") or os.environ.get("OBUS_OLLAMA_MODEL", "llama3.2"))
        emit("provider.started", {"provider": "ollama", "model": model})
        result = self._post_json(f"{endpoint}/api/generate", {"model": model, "prompt": task["objective"], "stream": False})
        output = str(result.get("response") or "").strip()
        if not output:
            raise RuntimeError("Ollama returned no response")
        return output

    def _run_openai_compatible(self, task: dict[str, Any], cancellation: threading.Event,
                               emit: Callable[[str, dict[str, Any]], None]) -> str:
        if cancellation.is_set():
            raise InterruptedError("task cancelled")
        endpoint = os.environ.get("OBUS_OPENAI_COMPATIBLE_URL", "").rstrip("/")
        if not endpoint:
            raise RuntimeError("OBUS_OPENAI_COMPATIBLE_URL is not configured")
        model = str(task.get("model") or os.environ.get("OBUS_OPENAI_COMPATIBLE_MODEL", "local-model"))
        token = os.environ.get("OBUS_OPENAI_COMPATIBLE_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        emit("provider.started", {"provider": "openai-compatible", "model": model})
        result = self._post_json(f"{endpoint}/chat/completions", {
            "model": model, "messages": [{"role": "user", "content": task["objective"]}], "stream": False,
        }, headers)
        choices = result.get("choices") or []
        output = str(choices[0].get("message", {}).get("content", "")).strip() if choices else ""
        if not output:
            raise RuntimeError("OpenAI-compatible provider returned no response")
        return output


class ObjectiveScheduler:
    """Durable interval scheduler which submits proactive objectives through the harness."""

    def __init__(self, database: Path, submit: Callable[..., dict[str, Any]], poll_seconds: float = 1.0):
        self.database = database
        self.submit = submit
        self.poll_seconds = max(0.1, poll_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS harness_objectives (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, objective TEXT NOT NULL,
                    workspace TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'codex',
                    interval_seconds INTEGER NOT NULL, priority INTEGER NOT NULL DEFAULT 50,
                    enabled INTEGER NOT NULL DEFAULT 1, next_run_at REAL NOT NULL,
                    last_run_at REAL, last_task_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_harness_objectives_due
                    ON harness_objectives(enabled, next_run_at);
            """)

    def create(self, name: str, objective: str, workspace: Path, interval_seconds: int,
               provider: str = "codex", priority: int = 50, enabled: bool = True) -> dict[str, Any]:
        now = time.time()
        item_id = uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_objectives(id,name,objective,workspace,provider,interval_seconds,priority,enabled,"
                "next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, name, objective, str(workspace.resolve()), provider, max(1, interval_seconds),
                 max(0, min(priority, 100)), int(enabled), now + max(1, interval_seconds), utc_now(), utc_now()),
            )
        return self.get(item_id)

    def get(self, item_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_objectives WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        return dict(row) | {"enabled": bool(row["enabled"])}

    def list(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM harness_objectives ORDER BY created_at DESC").fetchall()
        return [dict(row) | {"enabled": bool(row["enabled"])} for row in rows]

    def set_enabled(self, item_id: str, enabled: bool) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute("UPDATE harness_objectives SET enabled=?,updated_at=? WHERE id=?",
                                        (int(enabled), utc_now(), item_id))
            if cursor.rowcount == 0:
                raise KeyError(item_id)
        return self.get(item_id)

    def delete(self, item_id: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM harness_objectives WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                raise KeyError(item_id)

    def run_due(self, now: float | None = None) -> list[str]:
        current = time.time() if now is None else now
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_objectives WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at", (current,)
            ).fetchall()
        task_ids: list[str] = []
        for row in rows:
            task = self.submit(row["objective"], Path(row["workspace"]), source="scheduler",
                               priority=row["priority"], provider=row["provider"])
            task_ids.append(str(task["id"]))
            with self._connection() as connection:
                connection.execute(
                    "UPDATE harness_objectives SET last_run_at=?,last_task_id=?,next_run_at=?,updated_at=? WHERE id=?",
                    (current, task["id"], current + row["interval_seconds"], utc_now(), row["id"]),
                )
        return task_ids

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="obus-objective-scheduler", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            try:
                self.run_due()
            except Exception:
                continue

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
