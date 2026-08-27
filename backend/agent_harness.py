"""Durable autonomous task kernel for the OBus Warden runtime."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codex_policy import build_codex_exec_command
from .secret_safety import redact_text

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "interrupted"}
TASK_STATES = {"queued", "planning", "running", "verifying", "repairing", *TERMINAL_STATES}
RESUME_AFTER_INTERRUPTION_INSTRUCTION = (
    "This task was explicitly resumed after OBus restarted. Before taking any action, inspect the current "
    "workspace and the visible task history/checkpoint. Do not repeat or assume any uncertain side effect. "
    "Once a safe point is verified, continue ordinary local inspection, focused workspace edits, and local "
    "verification autonomously; do not ask for confirmation between those routine steps. Pause and clearly "
    "request approval before any destructive, external, credential-handling, or hardware-affecting action."
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class HarnessStore:
    """SQLite/WAL event store. Each operation owns its connection for thread safety."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS harness_tasks (
                    id TEXT PRIMARY KEY, objective TEXT NOT NULL, workspace TEXT NOT NULL,
                    state TEXT NOT NULL, source TEXT NOT NULL, priority INTEGER NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    started_at TEXT, finished_at TEXT, result TEXT, error TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS harness_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES harness_tasks(id)
                );
                CREATE TABLE IF NOT EXISTS harness_actions (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, capability TEXT NOT NULL,
                    intent TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT,
                    started_at TEXT NOT NULL, finished_at TEXT,
                    FOREIGN KEY(task_id) REFERENCES harness_tasks(id)
                );
                CREATE TABLE IF NOT EXISTS harness_lessons (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, objective TEXT NOT NULL,
                    content TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES harness_tasks(id)
                );
                CREATE TABLE IF NOT EXISTS harness_approvals (
                    id TEXT PRIMARY KEY, objective_sha256 TEXT NOT NULL,
                    objective_preview TEXT NOT NULL, workspace TEXT NOT NULL,
                    risks TEXT NOT NULL, provider TEXT NOT NULL, model TEXT,
                    priority INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
                    status TEXT NOT NULL, requested_at TEXT NOT NULL,
                    decided_at TEXT, decision_note TEXT, consumed_at TEXT,
                    task_id TEXT,
                    FOREIGN KEY(task_id) REFERENCES harness_tasks(id)
                );
                CREATE INDEX IF NOT EXISTS idx_harness_events_task ON harness_events(task_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_harness_tasks_state ON harness_tasks(state, priority, created_at);
                CREATE INDEX IF NOT EXISTS idx_harness_approvals_state ON harness_approvals(status, requested_at);
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(harness_tasks)")}
            if "provider" not in columns:
                connection.execute("ALTER TABLE harness_tasks ADD COLUMN provider TEXT NOT NULL DEFAULT 'codex'")
            if "model" not in columns:
                connection.execute("ALTER TABLE harness_tasks ADD COLUMN model TEXT")
            interrupted = connection.execute(
                "SELECT id FROM harness_tasks WHERE state IN ('queued','planning','running','verifying','repairing') "
                "AND cancel_requested=0"
            ).fetchall()
            if interrupted:
                now = utc_now()
                connection.execute(
                    "UPDATE harness_tasks SET state='interrupted',updated_at=?,error=? "
                    "WHERE state IN ('queued','planning','running','verifying','repairing') AND cancel_requested=0",
                    (now, "OBus restarted before this task completed. Inspect and resume explicitly."),
                )
                connection.executemany(
                    "INSERT INTO harness_events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                    [(row["id"], "task.interrupted", json.dumps({"reason": "runtime-restarted", "resume": "explicit-only"}), now)
                     for row in interrupted],
                )

    def create_task(self, objective: str, workspace: Path, source: str, priority: int, max_attempts: int,
                    provider: str = "codex", model: str | None = None) -> dict[str, Any]:
        task_id = uuid.uuid4().hex
        now = utc_now()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_tasks(id,objective,workspace,state,source,priority,max_attempts,created_at,updated_at,provider,model) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (task_id, objective, str(workspace), "queued", source, priority, max_attempts, now, now, provider, model),
            )
        self.add_event(task_id, "task.created", {"objective": objective, "workspace": str(workspace),
                                                  "source": source, "provider": provider, "model": model})
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        result = dict(row)
        result["cancel_requested"] = bool(result["cancel_requested"])
        return result

    def list_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_tasks ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        return [dict(row) | {"cancel_requested": bool(row["cancel_requested"])} for row in rows]

    def transition(self, task_id: str, state: str, **fields: Any) -> dict[str, Any]:
        if state not in TASK_STATES:
            raise ValueError(f"invalid harness state: {state}")
        current = self.get_task(task_id)
        values = (
            state,
            utc_now(),
            fields.get("attempt", current["attempt"]),
            fields.get("started_at", current["started_at"]),
            fields.get("finished_at", current["finished_at"]),
            fields.get("result", current["result"]),
            fields.get("error", current["error"]),
            task_id,
        )
        with self._connection() as connection:
            connection.execute(
                "UPDATE harness_tasks SET state=?,updated_at=?,attempt=?,started_at=?,"
                "finished_at=?,result=?,error=? WHERE id=?",
                values,
            )
        self.add_event(task_id, "task.state", {"state": state, **fields})
        return self.get_task(task_id)

    def request_cancel(self, task_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE harness_tasks SET cancel_requested=1,updated_at=? WHERE id=?", (utc_now(), task_id)
            )
            if cursor.rowcount == 0:
                raise KeyError(task_id)
        self.add_event(task_id, "task.cancel_requested", {})
        return self.get_task(task_id)

    def add_event(self, task_id: str, event_type: str, payload: dict[str, Any]) -> int:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO harness_events(task_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                (task_id, event_type, json.dumps(payload, ensure_ascii=False), utc_now()),
            )
            return int(cursor.lastrowid)

    def events(self, task_id: str, after: int = 0) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT sequence,event_type,payload,created_at FROM harness_events "
                "WHERE task_id=? AND sequence>? ORDER BY sequence", (task_id, after)
            ).fetchall()
        return [dict(row) | {"payload": json.loads(row["payload"])} for row in rows]

    def start_action(self, task_id: str, capability: str, intent: dict[str, Any]) -> str:
        action_id = uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_actions(id,task_id,capability,intent,status,started_at) VALUES(?,?,?,?,?,?)",
                (action_id, task_id, capability, json.dumps(intent), "running", utc_now()),
            )
        self.add_event(task_id, "action.started", {"action_id": action_id, "capability": capability, "intent": intent})
        return action_id

    def finish_action(self, task_id: str, action_id: str, status: str, receipt: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE harness_actions SET status=?,receipt=?,finished_at=? WHERE id=?",
                (status, json.dumps(receipt), utc_now(), action_id),
            )
        self.add_event(task_id, "action.finished", {"action_id": action_id, "status": status, "receipt": receipt})

    def promote_lesson(self, task_id: str, objective: str, content: str) -> dict[str, Any]:
        lesson = {"id": uuid.uuid4().hex, "task_id": task_id, "objective": objective, "content": content,
                  "active": True, "created_at": utc_now()}
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_lessons(id,task_id,objective,content,active,created_at) VALUES(?,?,?,?,1,?)",
                (lesson["id"], task_id, objective, content, lesson["created_at"]),
            )
        self.add_event(task_id, "lesson.promoted", {"lesson_id": lesson["id"]})
        return lesson

    def lessons(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_lessons WHERE active=1 ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) | {"active": bool(row["active"])} for row in rows]

    @staticmethod
    def _approval(row: sqlite3.Row) -> dict[str, Any]:
        approval = dict(row)
        approval["risks"] = json.loads(approval.pop("risks"))
        return approval

    def ensure_approval(self, objective: str, workspace: Path, risks: list[str], provider: str,
                        model: str | None, priority: int, max_attempts: int) -> dict[str, Any]:
        """Create or reuse one local, single-use approval request without retaining the full objective."""

        objective_sha256 = hashlib.sha256(objective.encode("utf-8")).hexdigest()
        risk_json = json.dumps(sorted(set(risks)), ensure_ascii=False)
        workspace_text = str(workspace.resolve())
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT * FROM harness_approvals WHERE objective_sha256=? AND workspace=? AND risks=? "
                "AND provider=? AND COALESCE(model,'')=COALESCE(?, '') AND priority=? AND max_attempts=? "
                "AND status IN ('pending','approved') ORDER BY requested_at DESC LIMIT 1",
                (objective_sha256, workspace_text, risk_json, provider, model, priority, max_attempts),
            ).fetchone()
            if existing is not None:
                return self._approval(existing)
            approval_id = "approval-" + uuid.uuid4().hex[:16]
            now = utc_now()
            connection.execute(
                "INSERT INTO harness_approvals(id,objective_sha256,objective_preview,workspace,risks,provider,model,"
                "priority,max_attempts,status,requested_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (approval_id, objective_sha256, redact_text(objective, 1200), workspace_text, risk_json, provider, model,
                 priority, max_attempts, "pending", now),
            )
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_approvals WHERE id=?", (approval_id,)).fetchone()
        if row is None:
            raise KeyError(approval_id)
        return self._approval(row)

    def list_approvals(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_approvals ORDER BY requested_at DESC LIMIT ?", (max(1, min(limit, 500)),)
            ).fetchall()
        return [self._approval(row) for row in rows]

    def decide_approval(self, approval_id: str, decision: str, note: str | None = None) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise ValueError("approval decision must be approved or rejected")
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE harness_approvals SET status=?,decided_at=?,decision_note=? WHERE id=? AND status='pending'",
                (decision, utc_now(), note or None, approval_id),
            )
        if cursor.rowcount == 0:
            existing = self.get_approval(approval_id)
            raise ValueError(f"approval is already {existing['status']}")
        return self.get_approval(approval_id)

    def consume_approval(self, approval_id: str, objective: str, workspace: Path, risks: list[str], provider: str,
                         model: str | None, priority: int, max_attempts: int) -> dict[str, Any]:
        """Consume an approved record only when it exactly matches the submitted one-time task."""

        objective_sha256 = hashlib.sha256(objective.encode("utf-8")).hexdigest()
        risk_json = json.dumps(sorted(set(risks)), ensure_ascii=False)
        workspace_text = str(workspace.resolve())
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None:
                raise KeyError(approval_id)
            approval = self._approval(row)
            expected = {
                "objective_sha256": objective_sha256, "workspace": workspace_text, "risks": sorted(set(risks)),
                "provider": provider, "model": model, "priority": priority, "max_attempts": max_attempts,
            }
            actual = {field: approval.get(field) for field in expected}
            if actual != expected:
                raise ValueError("approval does not match the current objective or task configuration")
            if approval["status"] != "approved":
                raise ValueError(f"approval is {approval['status']}; approve it locally before starting this task")
            connection.execute(
                "UPDATE harness_approvals SET status='consumed',consumed_at=? WHERE id=? AND status='approved'",
                (utc_now(), approval_id),
            )
        return self.get_approval(approval_id)

    def release_approval(self, approval_id: str) -> None:
        """Restore an unused approval if task creation fails after an exact-match claim."""

        with self._connection() as connection:
            connection.execute(
                "UPDATE harness_approvals SET status='approved',consumed_at=NULL WHERE id=? AND status='consumed' AND task_id IS NULL",
                (approval_id,),
            )

    def attach_approval_task(self, approval_id: str, task_id: str) -> None:
        with self._connection() as connection:
            connection.execute("UPDATE harness_approvals SET task_id=? WHERE id=? AND status='consumed'", (task_id, approval_id))


from backend.autonomy import ProviderRegistry
from backend.recovery import RecoveryManager


Runner = Callable[[dict[str, Any], threading.Event, Callable[[str, dict[str, Any]], None]], str]


class AgentHarnessRuntime:
    """Codex-primary autonomous runner with durable retry, cancellation, and learning."""

    def __init__(self, database: Path, runner: Runner | None = None, max_workers: int = 2):
        self.store = HarnessStore(database)
        self.recovery = RecoveryManager(database)
        self.providers = ProviderRegistry()
        self.runner = runner or self.providers.run
        self.runtime_config_resolver: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None
        self.max_workers = max(1, max_workers)
        self._lock = threading.Lock()
        self._threads: dict[str, threading.Thread] = {}
        self._cancellations: dict[str, threading.Event] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self.resume_queued()

    def submit(self, objective: str, workspace: Path, source: str = "local", priority: int = 50,
               max_attempts: int = 3, provider: str = "codex", model: str | None = None) -> dict[str, Any]:
        workspace = workspace.resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        supported = {item["id"] for item in self.providers.discover()}
        if provider not in supported:
            raise ValueError(f"unsupported provider: {provider}")
        task = self.store.create_task(objective, workspace, source, priority, max(1, min(max_attempts, 10)),
                                      provider, model)
        self._start(task["id"])
        return task

    def _task_with_runtime_config(self, task: dict[str, Any]) -> dict[str, Any]:
        """Resolve transient provider settings without persisting secrets or widening authority."""

        configured = dict(task)
        if self.runtime_config_resolver is None:
            return configured
        try:
            proposal = self.runtime_config_resolver(dict(task)) or {}
        except Exception:
            return configured
        if not isinstance(proposal, dict):
            return configured
        model = proposal.get("model")
        if isinstance(model, str) and model.strip():
            configured["model"] = model.strip()[:256]
        try:
            context_window = int(proposal.get("context_window") or 0)
        except (TypeError, ValueError):
            context_window = 0
        if 2_048 <= context_window <= 2_000_000:
            configured["context_window"] = context_window
        return configured

    def resume_queued(self) -> None:
        for task in reversed(self.store.list_tasks(500)):
            if task["state"] == "queued" and not task["cancel_requested"]:
                self._start(task["id"])

    def resume(self, task_id: str) -> dict[str, Any]:
        """Resume a previously interrupted ordinary task only after a new local UI action."""

        task = self.store.get_task(task_id)
        if task["state"] != "interrupted" or task["cancel_requested"]:
            raise ValueError("only an interrupted task without a cancellation request can be resumed")
        resumed = self.store.transition(task_id, "queued", error=None, finished_at=None)
        self.store.add_event(task_id, "task.resume_requested", {"explicit": True, "safe_reinspection": True})
        self._start(task_id, resumed=True)
        return self.store.get_task(task_id)

    def _start(self, task_id: str, resumed: bool = False) -> None:
        with self._lock:
            if task_id in self._threads and self._threads[task_id].is_alive():
                return
            active = sum(thread.is_alive() for thread in self._threads.values())
            if active >= self.max_workers:
                return
            cancellation = threading.Event()
            thread = threading.Thread(target=self._worker_entry, args=(task_id, cancellation, resumed), daemon=True,
                                      name=f"obus-harness-{task_id[:8]}")
            self._cancellations[task_id] = cancellation
            self._threads[task_id] = thread
            thread.start()

    def _worker_entry(self, task_id: str, cancellation: threading.Event, resumed: bool = False) -> None:
        try:
            self._execute(task_id, cancellation, resumed)
        finally:
            with self._lock:
                self._threads.pop(task_id, None)
                self._cancellations.pop(task_id, None)
            for queued in reversed(self.store.list_tasks(500)):
                if queued["state"] == "queued" and not queued["cancel_requested"]:
                    self._start(queued["id"])
                    break

    def _execute(self, task_id: str, cancellation: threading.Event, resumed: bool = False) -> None:
        task = self.store.get_task(task_id)
        if task["cancel_requested"]:
            self.store.transition(task_id, "cancelled", finished_at=utc_now())
            return
        self.store.transition(task_id, "planning", started_at=task["started_at"] or utc_now())
        for attempt in range(int(task["attempt"]) + 1, int(task["max_attempts"]) + 1):
            if cancellation.is_set() or self.store.get_task(task_id)["cancel_requested"]:
                self.store.transition(task_id, "cancelled", attempt=attempt, finished_at=utc_now())
                return
            state = "running" if attempt == 1 else "repairing"
            self.store.transition(task_id, state, attempt=attempt)
            checkpoint = self.recovery.create(task_id, Path(task["workspace"]))
            self.store.add_event(task_id, "checkpoint.created", {
                "checkpoint_id": checkpoint["id"], "files": checkpoint["files_copied"],
                "bytes": checkpoint["bytes_copied"], "skipped": checkpoint["files_skipped"],
            })
            runtime_task = self._task_with_runtime_config(task)
            if resumed:
                runtime_task["resumed_after_interruption"] = True
                self.store.add_event(task_id, "task.resumed", {"explicit": True, "safe_reinspection": True})
            provider = str(runtime_task.get("provider") or "codex")
            if runtime_task.get("context_window"):
                self.store.add_event(task_id, "provider.configured", {
                    "provider": provider, "model": runtime_task.get("model"),
                    "context_window": runtime_task["context_window"],
                })
            action_id = self.store.start_action(task_id, f"{provider}.guarded-autonomous", {
                "objective": task["objective"], "workspace": task["workspace"], "attempt": attempt,
                "provider": provider, "model": runtime_task.get("model"),
                "context_window": runtime_task.get("context_window"), "checkpoint_id": checkpoint["id"],
            })
            try:
                result = self.runner(runtime_task | {"attempt": attempt}, cancellation,
                                     lambda kind, payload: self.store.add_event(task_id, kind, payload))
                if cancellation.is_set():
                    raise InterruptedError("task cancelled")
                verification = self.recovery.verify_workspace(checkpoint["id"])
                self.store.add_event(task_id, "workspace.verified", verification)
                if verification["status"] == "failed":
                    raise RuntimeError(verification.get("reason") or "workspace verification failed")
                checkpoint_receipt = self.recovery.complete(checkpoint["id"])
                self.store.finish_action(task_id, action_id, "succeeded", {
                    "result": result[-8000:], "checkpoint": checkpoint_receipt, "verification": verification,
                })
                self.store.transition(task_id, "verifying", attempt=attempt)
                lesson = self.store.promote_lesson(task_id, task["objective"], result[-16000:])
                self.store.add_event(task_id, "task.completed", {"lesson_id": lesson["id"]})
                # A terminal state is the public signal that no more durable work is
                # pending for this task.  Keep it as the final write: otherwise a
                # caller that observes "succeeded" can tear down its workspace while
                # this worker still owns the SQLite database on Windows.
                self.store.transition(task_id, "succeeded", attempt=attempt, result=result,
                                      finished_at=utc_now(), error=None)
                return
            except InterruptedError as exc:
                rollback = self.recovery.rollback(checkpoint["id"])
                self.store.finish_action(task_id, action_id, "cancelled", {
                    "error": str(exc), "rollback": rollback,
                })
                self.store.transition(task_id, "cancelled", attempt=attempt, error=str(exc), finished_at=utc_now())
                return
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                rollback = self.recovery.rollback(checkpoint["id"])
                failure = self.recovery.record_failure(task_id, exc)
                self.store.finish_action(task_id, action_id, "failed", {
                    "error": error, "rollback": rollback, "failure": failure,
                })
                self.store.add_event(task_id, "repair.required", {
                    "attempt": attempt, "error": error, "rollback": rollback,
                    "fingerprint": failure["fingerprint"], "circuit_open": failure["circuit_open"],
                })
                if failure["circuit_open"] or attempt >= int(task["max_attempts"]):
                    final_error = f"circuit breaker opened: {error}" if failure["circuit_open"] else error
                    self.store.transition(task_id, "failed", attempt=attempt, error=final_error,
                                          finished_at=utc_now())
                    return
                time.sleep(min(attempt, 3))
        self.store.transition(task_id, "failed", error="repair budget exhausted", finished_at=utc_now())

    def cancel(self, task_id: str) -> dict[str, Any]:
        task = self.store.request_cancel(task_id)
        with self._lock:
            event = self._cancellations.get(task_id)
            process = self._processes.get(task_id)
        if event:
            event.set()
        if process and process.poll() is None:
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()
        return task

    def _run_codex(self, task: dict[str, Any], cancellation: threading.Event,
                   emit: Callable[[str, dict[str, Any]], None]) -> str:
        executable = os.environ.get("OBUS_CODEX_COMMAND", "codex")
        model = os.environ.get("OBUS_CODEX_MODEL", "")
        with tempfile.NamedTemporaryFile(prefix="obus-harness-", suffix=".txt", delete=False) as handle:
            output_path = Path(handle.name)
        prompt = task["objective"]
        if task.get("resumed_after_interruption"):
            prompt = f"{RESUME_AFTER_INTERRUPTION_INSTRUCTION}\n\nObjective:\n{prompt}"
        if int(task["attempt"]) > 1:
            prompt += "\n\nPrevious autonomous attempt failed. Diagnose the current workspace state, repair it, verify the result, and finish the objective."
        command = build_codex_exec_command(
            executable,
            prompt,
            model=model or None,
            output_path=output_path,
        )
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        emit("codex.started", {"command": executable, "model": model or "default"})
        process = subprocess.Popen(command, cwd=task["workspace"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", creationflags=creationflags)
        with self._lock:
            self._processes[task["id"]] = process
        try:
            while process.poll() is None:
                if cancellation.wait(0.25):
                    raise InterruptedError("task cancelled")
            stdout = process.stdout.read() if process.stdout else ""
            if stdout:
                emit("codex.output", {"text": stdout[-16000:]})
            result = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.exists() else ""
            if process.returncode != 0 or not result:
                raise RuntimeError(f"Codex exited with code {process.returncode}: {stdout[-2000:]}")
            return result
        finally:
            with self._lock:
                self._processes.pop(task["id"], None)
            output_path.unlink(missing_ok=True)

    def health(self) -> dict[str, Any]:
        with self._lock:
            active = sum(thread.is_alive() for thread in self._threads.values())
        return {"status": "ready", "mode": "guarded-autonomous", "authority": "workspace-write",
                "active_tasks": active, "max_workers": self.max_workers, "database": str(self.store.path),
                "provider_default": "codex", "providers": self.providers.capabilities()}
