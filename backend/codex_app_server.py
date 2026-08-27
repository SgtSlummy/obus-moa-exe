"""A small, local JSONL client for the optional Codex App Server bridge.

This is intentionally a narrow host, not a second agent runtime.  Codex owns
its persisted conversation state; OBus owns the visible workspace boundary,
event feed, and approval hold.  A bridge process is created only by an
explicit local user action and no model turn starts during its handshake.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from .execution_policy import classify_major_risk
from .secret_safety import redact_text


MAX_EVENTS = 1_000
MAX_EVENT_TEXT = 16_000
MAX_SYNTHESIS_FINDINGS = 24
MAX_SYNTHESIS_TEXT = 12_000
REQUEST_TIMEOUT_SECONDS = 15


class CodexAppServerError(RuntimeError):
    """Raised for a failed or unavailable local App Server operation."""


def _safe_value(value: Any) -> Any:
    """Bound and redact data before it becomes part of the dashboard feed."""

    if isinstance(value, str):
        return redact_text(value, min(MAX_EVENT_TEXT, max(1, len(value))), parse_json=False)
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:100]]
    if isinstance(value, dict):
        return {str(key)[:128]: _safe_value(item) for key, item in list(value.items())[:100]}
    return value


class CodexAppServer:
    """Own one optional App Server child and expose its safe UI state."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._event_sequence = 0
        self._threads: dict[str, dict[str, str]] = {}
        self._approvals: dict[str, dict[str, Any]] = {}

    def _record(self, method: str, params: Any) -> None:
        with self._lock:
            self._event_sequence += 1
            self._events.append(
                {
                    "sequence": self._event_sequence,
                    "at": time.time(),
                    "method": method[:160],
                    "params": _safe_value(params),
                }
            )

    def _write(self, message: dict[str, Any]) -> None:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None or process.stdin is None:
                raise CodexAppServerError("Codex App Server is not running")
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()

    def _read_stdout(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for raw_line in process.stdout:
            try:
                message = json.loads(raw_line)
            except json.JSONDecodeError:
                self._record("app-server/invalid-output", {"text": raw_line[-MAX_EVENT_TEXT:]})
                continue
            if isinstance(message, dict) and "id" in message and ("result" in message or "error" in message):
                with self._lock:
                    waiting = self._pending.pop(message["id"], None)
                if waiting is not None:
                    waiting.put(message)
                    continue
            if isinstance(message, dict) and "method" in message and "id" in message:
                self._handle_server_request(message)
                continue
            method = str(message.get("method") or "app-server/message") if isinstance(message, dict) else "app-server/message"
            params = message.get("params", message) if isinstance(message, dict) else message
            self._track_turn_state(method, params)
            self._record(method, params)
        self._record("app-server/exited", {"returncode": process.poll()})

    def _read_stderr(self, process: subprocess.Popen[str]) -> None:
        assert process.stderr is not None
        for raw_line in process.stderr:
            self._record("app-server/stderr", {"text": raw_line[-MAX_EVENT_TEXT:]})

    def _handle_server_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        server_request_id = message.get("id")
        is_command = method == "item/commandExecution/requestApproval"
        is_file_change = method == "item/fileChange/requestApproval"
        if is_command or is_file_change:
            command = str(params.get("command") or "")
            reason = str(params.get("reason") or "")
            network = params.get("networkApprovalContext")
            risks = classify_major_risk("\n".join(part for part in (command, reason) if part))
            # OBus may continue ordinary workspace work independently.  It
            # never silently grants network, major destructive, or hardware
            # authority; those decisions are surfaced in the local UI.
            if not risks and not network:
                self._write({"id": server_request_id, "result": {"decision": "accept"}})
                self._record(
                    "approval/auto-accepted",
                    {"request_method": method, "command": command, "reason": reason},
                )
                return
            approval_id = "codex-approval-" + uuid.uuid4().hex[:12]
            approval = {
                "id": approval_id,
                "server_request_id": server_request_id,
                "method": method,
                "thread_id": str(params.get("threadId") or ""),
                "turn_id": str(params.get("turnId") or ""),
                "command": command,
                "reason": reason,
                "network": _safe_value(network),
                "risks": risks,
                "status": "pending",
            }
            with self._lock:
                self._approvals[approval_id] = approval
            self._record("approval/required", approval)
            return
        # Other server requests, including permission grants and tool forms,
        # require explicit user interaction.  Keep their metadata visible but
        # do not fabricate a response with an incompatible schema.
        self._record("server-request/needs-user", {"request_method": method, "params": params})

    def _track_turn_state(self, method: str, params: Any) -> None:
        if not isinstance(params, dict) or not method.startswith("turn/"):
            return
        thread_id = str(params.get("threadId") or "")
        turn = params.get("turn") if isinstance(params.get("turn"), dict) else params
        turn_id = str(turn.get("id") or params.get("turnId") or "") if isinstance(turn, dict) else ""
        if not thread_id or not turn_id:
            return
        with self._lock:
            thread = self._threads.get(thread_id)
            if thread is None:
                return
            if method == "turn/started":
                thread["active_turn"] = turn_id
                thread["status"] = "running"
            elif method == "turn/completed":
                if thread.get("active_turn") == turn_id:
                    thread.pop("active_turn", None)
                thread["status"] = str(turn.get("status") or "completed")

    def _request(self, method: str, params: dict[str, Any], timeout: int = REQUEST_TIMEOUT_SECONDS) -> dict[str, Any]:
        with self._lock:
            request_id = self._next_id
            self._next_id += 1
            waiting: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = waiting
        try:
            self._write({"method": method, "id": request_id, "params": params})
            try:
                response = waiting.get(timeout=timeout)
            except queue.Empty as exc:
                raise CodexAppServerError(f"Codex App Server timed out while calling {method}") from exc
            if "error" in response:
                error = response.get("error")
                raise CodexAppServerError(str(error.get("message") if isinstance(error, dict) else error))
            result = response.get("result")
            if not isinstance(result, dict):
                raise CodexAppServerError(f"Codex App Server returned an invalid {method} response")
            return result
        finally:
            with self._lock:
                self._pending.pop(request_id, None)

    def ensure_started(self, command: list[str]) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return
            self._process = subprocess.Popen(
                [*command, "--stdio"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            process = self._process
        threading.Thread(target=self._read_stdout, args=(process,), daemon=True, name="obus-codex-app-server-out").start()
        threading.Thread(target=self._read_stderr, args=(process,), daemon=True, name="obus-codex-app-server-err").start()
        try:
            self._request(
                "initialize",
                {"clientInfo": {"name": "obus", "title": "OBus", "version": "1.0"}},
            )
            self._write({"method": "initialized", "params": {}})
        except Exception:
            self.close()
            raise
        self._record("app-server/ready", {"transport": "stdio"})

    def start_thread(self, workspace: Path, model: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "cwd": str(workspace),
            "sandbox": "workspace-write",
            "approvalPolicy": "on-request",
            "serviceName": "obus",
        }
        if model:
            params["model"] = model
        result = self._request("thread/start", params)
        thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
        thread_id = str(thread.get("id") or "")
        if not thread_id:
            raise CodexAppServerError("Codex App Server did not return a thread id")
        with self._lock:
            self._threads[thread_id] = {"workspace": str(workspace), "status": "idle"}
        self._record("thread/attached", {"thread_id": thread_id, "workspace": str(workspace)})
        return _safe_value(thread)

    def resume_thread(self, thread_id: str, workspace: Path, model: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "cwd": str(workspace),
            "sandbox": "workspace-write",
            "approvalPolicy": "on-request",
            "serviceName": "obus",
        }
        if model:
            params["model"] = model
        result = self._request("thread/resume", params)
        thread = result.get("thread") if isinstance(result.get("thread"), dict) else {}
        resumed_id = str(thread.get("id") or thread_id)
        if resumed_id != thread_id:
            raise CodexAppServerError("Codex App Server resumed an unexpected thread")
        with self._lock:
            self._threads[thread_id] = {"workspace": str(workspace), "status": str(thread.get("status") or "idle")}
        self._record("thread/resumed", {"thread_id": thread_id, "workspace": str(workspace)})
        return _safe_value(thread)

    def start_turn(
        self,
        thread_id: str,
        prompt: str,
        workspace: Path,
        model: str | None = None,
        *,
        read_only: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            thread = self._threads.get(thread_id)
        if thread is None:
            raise CodexAppServerError("Codex thread is not attached to this OBus session")
        if Path(thread["workspace"]).resolve() != workspace.resolve():
            raise CodexAppServerError("Codex thread belongs to a different workspace")
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(workspace),
            "approvalPolicy": "on-request",
            "sandboxPolicy": (
                {"type": "readOnly", "networkAccess": False}
                if read_only
                else {
                    "type": "workspaceWrite",
                    "writableRoots": [str(workspace)],
                    "networkAccess": False,
                }
            ),
        }
        if model:
            params["model"] = model
        result = self._request("turn/start", params)
        turn = result.get("turn") if isinstance(result.get("turn"), dict) else {}
        turn_id = str(turn.get("id") or "")
        if turn_id:
            with self._lock:
                self._threads[thread_id]["active_turn"] = turn_id
                self._threads[thread_id]["status"] = "running"
        self._record(
            "turn/submitted",
            {"thread_id": thread_id, "workspace": str(workspace), "read_only": read_only},
        )
        return _safe_value(turn if turn else result)

    def interrupt_turn(self, thread_id: str, workspace: Path) -> dict[str, Any]:
        with self._lock:
            thread = self._threads.get(thread_id)
        if thread is None or Path(thread["workspace"]).resolve() != workspace.resolve():
            raise CodexAppServerError("Codex thread belongs to a different workspace")
        turn_id = str(thread.get("active_turn") or "")
        if not turn_id:
            raise CodexAppServerError("Codex thread has no active turn to interrupt")
        self._request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
        with self._lock:
            thread["status"] = "interrupting"
        self._record("turn/interruption-requested", {"thread_id": thread_id, "turn_id": turn_id})
        return {"thread_id": thread_id, "turn_id": turn_id, "status": "interrupting"}

    def events(self, after: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            return [event for event in self._events if int(event["sequence"]) > after]

    def worker_findings(self, thread_ids: list[str], workspace: Path, *, minimum_threads: int = 2) -> list[dict[str, str]]:
        """Return bounded redacted text emitted by selected completed workers only."""

        selected = {str(thread_id).strip() for thread_id in thread_ids if str(thread_id).strip()}
        if len(selected) < minimum_threads:
            raise CodexAppServerError("Select enough distinct completed Codex threads for this handoff")
        root = workspace.resolve()
        with self._lock:
            for thread_id in selected:
                thread = self._threads.get(thread_id)
                if thread is None or Path(thread.get("workspace", "")).resolve() != root:
                    raise CodexAppServerError("Codex worker belongs to a different workspace or is no longer attached")
                if thread.get("active_turn"):
                    raise CodexAppServerError("Wait for every selected read-only worker to finish before synthesizing")
            snapshot = list(self._events)

        findings: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        budget = MAX_SYNTHESIS_TEXT
        for event in snapshot:
            params = event.get("params") if isinstance(event.get("params"), dict) else {}
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            item = params.get("item") if isinstance(params.get("item"), dict) else {}
            thread_id = str(params.get("threadId") or params.get("thread_id") or turn.get("threadId") or turn.get("thread_id") or item.get("threadId") or item.get("thread_id") or "")
            if thread_id not in selected:
                continue
            text = next((value for value in (params.get("delta"), params.get("text"), params.get("message"), item.get("delta"), item.get("text"), item.get("message")) if isinstance(value, str) and value.strip()), "")
            compact = " ".join(str(text).split())
            if not compact:
                continue
            compact = redact_text(compact, min(2_000, budget), parse_json=False)
            key = (thread_id, compact)
            if key in seen:
                continue
            seen.add(key)
            findings.append({"thread_id": thread_id, "text": compact})
            budget -= len(compact)
            if budget <= 0 or len(findings) >= MAX_SYNTHESIS_FINDINGS:
                break
        if not findings:
            raise CodexAppServerError("Selected workers have not emitted any bounded findings yet")
        return findings

    def thread_findings(self, thread_id: str, workspace: Path) -> list[dict[str, str]]:
        """Read one completed, attached thread for an explicitly requested handoff."""

        return self.worker_findings([thread_id], workspace, minimum_threads=1)

    def decide(self, approval_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accept", "acceptForSession", "decline", "cancel"}:
            raise CodexAppServerError("unsupported approval decision")
        with self._lock:
            approval = self._approvals.get(approval_id)
        if approval is None or approval.get("status") != "pending":
            raise CodexAppServerError("Codex approval is no longer pending")
        self._write({"id": approval["server_request_id"], "result": {"decision": decision}})
        with self._lock:
            approval["status"] = decision
        self._record("approval/decided", {"approval_id": approval_id, "decision": decision})
        return _safe_value(approval)

    def status(self, available: bool) -> dict[str, Any]:
        with self._lock:
            process = self._process
            running = bool(process is not None and process.poll() is None)
            approvals = [_safe_value(item) for item in self._approvals.values() if item.get("status") == "pending"]
            return {
                "available": available,
                "running": running,
                "pid": process.pid if running and process else None,
                "threads": [{"id": key, **value} for key, value in self._threads.items()],
                "pending_approvals": approvals,
                "event_cursor": self._event_sequence,
                "transport": "stdio",
            }

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
            pending = list(self._pending.values())
            self._pending.clear()
        for waiting in pending:
            waiting.put({"error": {"message": "Codex App Server stopped"}})
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        self._record("app-server/stopped", {})
