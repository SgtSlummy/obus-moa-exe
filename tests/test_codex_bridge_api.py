from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend
import backend.codex_bridge_api as bridge_api


class _Bridge:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.thread_count = 0

    def status(self, available):
        return {"available": available, "running": False, "threads": [], "pending_approvals": [], "event_cursor": 0, "transport": "stdio"}

    def ensure_started(self, command):
        self.calls.append(("start", command))

    def start_thread(self, workspace, model):
        self.calls.append(("thread", workspace, model))
        self.thread_count += 1
        return {"id": "thr-obus" if self.thread_count == 1 else f"thr-obus-{self.thread_count}"}

    def resume_thread(self, thread_id, workspace, model):
        self.calls.append(("resume", thread_id, workspace, model))
        return {"id": thread_id, "status": "idle"}

    def start_turn(self, thread_id, prompt, workspace, model, *, read_only=False):
        self.calls.append(("turn-read-only" if read_only else "turn", thread_id, prompt, workspace, model))
        return {"id": "turn-obus", "status": "inProgress"}

    def worker_findings(self, thread_ids, workspace):
        self.calls.append(("findings", thread_ids, workspace))
        return [{"thread_id": thread_id, "text": f"finding from {thread_id}"} for thread_id in thread_ids]

    def thread_findings(self, thread_id, workspace):
        self.calls.append(("thread-findings", thread_id, workspace))
        return [{"thread_id": thread_id, "text": "ordinary workspace repair and verification"}]

    def interrupt_turn(self, thread_id, workspace):
        self.calls.append(("interrupt", thread_id, workspace))
        return {"thread_id": thread_id, "status": "interrupting"}

    def events(self, after):
        return [{"sequence": after + 1, "method": "item/agentMessage/delta", "params": {"delta": "ready"}}]

    def decide(self, approval_id, decision):
        return {"id": approval_id, "status": decision}

    def close(self):
        self.calls.append(("close",))


def test_bridge_needs_workspace_and_starts_only_on_explicit_thread_request(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    client = TestClient(backend.app)

    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: None)
    blocked = client.post("/api/codex-bridge/threads", json={})
    assert blocked.status_code == 409
    assert stub.calls == []

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))
    created = client.post("/api/codex-bridge/threads", json={"model": "gpt-test"})
    turn = client.post("/api/codex-bridge/threads/thr-obus/turns", json={"prompt": "inspect this workspace"})

    assert created.status_code == 201
    assert turn.status_code == 202
    assert stub.calls[0] == ("start", ["codex", "app-server"])
    assert stub.calls[1] == ("thread", workspace.resolve(), "gpt-test")
    assert stub.calls[2] == ("turn", "thr-obus", "inspect this workspace", workspace.resolve(), None)


def test_parallel_bridge_starts_isolated_read_only_threads_for_an_ordinary_goal(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    remembered = []

    class Store:
        def remember(self, *args):
            remembered.append(args)
            return {}

    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(bridge_api, "thread_store", Store())
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))
    client = TestClient(backend.app)

    response = client.post("/api/codex-bridge/parallel", json={"prompt": "Review the workspace safely", "model": "gpt-test", "workers": 3})

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "started"
    assert payload["execution"] == "isolated-read-only-codex-threads"
    assert len(payload["workers"]) == 3
    assert len(remembered) == 3
    assert [call[0] for call in stub.calls] == ["start", "thread", "turn-read-only", "thread", "turn-read-only", "thread", "turn-read-only"]
    assert all("private" in call[2].lower() for call in stub.calls if call[0] == "turn-read-only")


def test_parallel_bridge_rejects_major_risk_before_starting_app_server(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))

    response = TestClient(backend.app).post("/api/codex-bridge/parallel", json={"prompt": "Increase nvidia GPU power limit before reviewing the workspace"})

    assert response.status_code == 409
    assert "hardware_safety_controls" in response.json()["detail"]["risks"]
    assert stub.calls == []


def test_parallel_bridge_synthesis_uses_selected_workers_in_a_new_read_only_thread(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))

    class Store:
        def remember(self, *args):
            return {}

    monkeypatch.setattr(bridge_api, "thread_store", Store())
    response = TestClient(backend.app).post(
        "/api/codex-bridge/parallel/synthesize",
        json={"worker_thread_ids": ["thr-a", "thr-b"], "model": "gpt-test"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["execution"] == "separate-read-only-codex-synthesis"
    assert payload["worker_count"] == 2
    assert [call[0] for call in stub.calls] == ["findings", "start", "thread", "turn-read-only"]
    assert "read-only synthesis" in stub.calls[-1][2].lower()


def test_completed_synthesis_promotes_only_an_explicit_ordinary_workspace_task(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))

    class Store:
        def remember(self, *args):
            return {}

    monkeypatch.setattr(bridge_api, "thread_store", Store())
    response = TestClient(backend.app).post("/api/codex-bridge/threads/thr-synthesis/promote", json={"model": "gpt-test"})

    assert response.status_code == 202
    payload = response.json()
    assert payload["execution"] == "explicit-reviewed-workspace-task"
    assert payload["network"] == "disabled"
    assert [call[0] for call in stub.calls] == ["thread-findings", "start", "thread", "turn"]
    assert "explicitly asked" in stub.calls[-1][2].lower()


def test_reviewed_task_promotion_blocks_hardware_risk_before_starting_app_server(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))
    stub.thread_findings = lambda _thread_id, _workspace: [{"thread_id": "thr", "text": "Increase nvidia GPU power limit"}]

    response = TestClient(backend.app).post("/api/codex-bridge/threads/thr-synthesis/promote", json={})

    assert response.status_code == 409
    assert "hardware_safety_controls" in response.json()["detail"]["risks"]
    assert stub.calls == []


def test_bridge_status_and_events_are_local_read_only(monkeypatch):
    stub = _Bridge()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    client = TestClient(backend.app)

    status = client.get("/api/codex-bridge/status")
    events = client.get("/api/codex-bridge/events?after=7")

    assert status.status_code == 200
    assert status.json()["available"] is True
    assert events.json()["events"][0]["sequence"] == 8


def test_bridge_resumes_only_a_thread_recorded_for_the_selected_workspace(tmp_path: Path, monkeypatch):
    stub = _Bridge()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(bridge_api, "bridge", stub)
    monkeypatch.setattr(backend.app.state, "codex_command_provider", lambda *args: ["codex", *args])
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))

    class Store:
        def contains(self, thread_id, root):
            return thread_id == "thr-saved" and root == workspace.resolve()

        def remember(self, *args):
            return {}

        def recent(self, _root):
            return []

    monkeypatch.setattr(bridge_api, "thread_store", Store())
    client = TestClient(backend.app)
    missing = client.post("/api/codex-bridge/threads/thr-other/resume", json={})
    resumed = client.post("/api/codex-bridge/threads/thr-saved/resume", json={"model": "gpt-test"})
    interrupted = client.post("/api/codex-bridge/threads/thr-saved/interrupt")

    assert missing.status_code == 404
    assert resumed.status_code == 200
    assert interrupted.status_code == 202
    assert stub.calls[0] == ("start", ["codex", "app-server"])
    assert stub.calls[1] == ("resume", "thr-saved", workspace.resolve(), "gpt-test")
    assert stub.calls[2] == ("interrupt", "thr-saved", workspace.resolve())
