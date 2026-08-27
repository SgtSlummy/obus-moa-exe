from __future__ import annotations

from pathlib import Path

from backend.codex_app_server import CodexAppServer


class _Input:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def write(self, value: str) -> None:
        self.messages.append(value)

    def flush(self) -> None:
        pass


class _Process:
    def __init__(self) -> None:
        self.stdin = _Input()
        self.pid = 4321

    def poll(self):
        return None


def _bridge_with_process() -> tuple[CodexAppServer, _Process]:
    bridge = CodexAppServer()
    process = _Process()
    bridge._process = process  # type: ignore[assignment]
    return bridge, process


def test_read_only_turn_is_bound_to_its_workspace_and_disables_network(tmp_path: Path):
    bridge = CodexAppServer()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    other_workspace = tmp_path / "other"
    other_workspace.mkdir()
    bridge._threads["thread-safe"] = {"workspace": str(workspace.resolve()), "status": "idle"}
    requests = []

    def request(method, params, timeout=15):
        requests.append((method, params, timeout))
        return {"turn": {"id": "turn-safe", "status": "inProgress"}}

    bridge._request = request  # type: ignore[method-assign]
    turn = bridge.start_turn("thread-safe", "Inspect only", workspace, read_only=True)

    assert turn["id"] == "turn-safe"
    method, params, _timeout = requests[0]
    assert method == "turn/start"
    assert params["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}

    try:
        bridge.start_turn("thread-safe", "Do not cross workspaces", other_workspace, read_only=True)
    except Exception as exc:
        assert "different workspace" in str(exc)
    else:
        raise AssertionError("a bridge thread must stay bound to its selected workspace")


def test_ordinary_command_approval_is_local_automatic_but_hardware_risk_holds_for_user():
    bridge, process = _bridge_with_process()

    bridge._handle_server_request(
        {"id": 7, "method": "item/commandExecution/requestApproval", "params": {"command": "pytest -q", "reason": "run tests"}}
    )
    assert process.stdin.messages == ['{"id":7,"result":{"decision":"accept"}}\n']
    assert bridge.status(True)["pending_approvals"] == []

    bridge._handle_server_request(
        {
            "id": 8,
            "method": "item/commandExecution/requestApproval",
            "params": {"command": "nvidia-smi -pl 450", "reason": "increase GPU power limit"},
        }
    )
    pending = bridge.status(True)["pending_approvals"]
    assert len(pending) == 1
    assert "hardware_safety_controls" in pending[0]["risks"]
    assert len(process.stdin.messages) == 1

    decision = bridge.decide(pending[0]["id"], "decline")
    assert decision["status"] == "decline"
    assert process.stdin.messages[-1] == '{"id":8,"result":{"decision":"decline"}}\n'


def test_worker_findings_are_workspace_bound_and_require_completed_workers(tmp_path: Path):
    bridge = CodexAppServer()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bridge._threads.update({
        "worker-a": {"workspace": str(workspace.resolve()), "status": "completed"},
        "worker-b": {"workspace": str(workspace.resolve()), "status": "completed"},
    })
    bridge._record("item/agentMessage/delta", {"threadId": "worker-a", "delta": "inspect the API surface"})
    bridge._record("item/agentMessage/delta", {"threadId": "worker-b", "delta": "verify focused tests"})

    findings = bridge.worker_findings(["worker-a", "worker-b"], workspace)

    assert findings == [
        {"thread_id": "worker-a", "text": "inspect the API surface"},
        {"thread_id": "worker-b", "text": "verify focused tests"},
    ]
    bridge._threads["worker-b"]["active_turn"] = "turn-running"
    try:
        bridge.worker_findings(["worker-a", "worker-b"], workspace)
    except Exception as exc:
        assert "finish" in str(exc)
    else:
        raise AssertionError("running workers must not be synthesized")


def test_completed_thread_findings_allow_one_explicit_handoff(tmp_path: Path):
    bridge = CodexAppServer()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bridge._threads["synthesis"] = {"workspace": str(workspace.resolve()), "status": "completed"}
    bridge._record("item/agentMessage/delta", {"threadId": "synthesis", "delta": "apply the tested ordinary repair"})

    findings = bridge.thread_findings("synthesis", workspace)

    assert findings == [{"thread_id": "synthesis", "text": "apply the tested ordinary repair"}]
