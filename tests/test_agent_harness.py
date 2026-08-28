import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent_harness import AgentHarnessRuntime, HarnessStore
from backend.autonomy import ProviderRegistry
import backend.harness_api as harness_api


def wait_for_state(runtime: AgentHarnessRuntime, task_id: str, terminal=True, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = runtime.store.get_task(task_id)
        if (task["state"] in {"succeeded", "failed", "cancelled"}) == terminal:
            return task
        time.sleep(0.02)
    raise AssertionError(f"task did not reach expected state: {runtime.store.get_task(task_id)}")


def test_harness_persists_receipts_events_and_immediately_promoted_learning(tmp_path: Path):
    def successful_runner(task, cancellation, emit):
        assert task["workspace"] == str(tmp_path.resolve())
        assert not cancellation.is_set()
        emit("tool.output", {"text": "verified"})
        return "Implemented and verified the objective"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=successful_runner)
    task = runtime.submit("Repair the repository", tmp_path)
    completed = wait_for_state(runtime, task["id"])

    assert completed["state"] == "succeeded"
    assert completed["attempt"] == 1
    event_types = [event["event_type"] for event in runtime.store.events(task["id"])]
    assert "action.started" in event_types
    assert "action.finished" in event_types
    assert "workspace.verified" in event_types
    assert "lesson.promoted" in event_types
    lessons = runtime.store.lessons()
    assert lessons[0]["task_id"] == task["id"]
    assert lessons[0]["active"] is True


def test_harness_persists_inspect_work_verify_workflow_evidence(tmp_path: Path):
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda *_args: "done")
    task = runtime.submit("inspect, change, and verify", tmp_path)
    completed = wait_for_state(runtime, task["id"])

    assert completed["workflow"] == "inspect-work-verify/v1"
    stages = [event["payload"] for event in runtime.store.events(task["id"])
              if event["event_type"] == "workflow.stage"]
    assert [(stage["stage"], stage["status"]) for stage in stages] == [
        ("inspect", "started"), ("inspect", "succeeded"),
        ("work", "started"), ("work", "succeeded"),
        ("verify", "started"), ("verify", "succeeded"),
    ]


def test_harness_resolves_ephemeral_provider_context_before_running_task(tmp_path: Path):
    received: list[dict] = []

    def runner(task, _cancellation, _emit):
        received.append(task)
        return "completed with resolved local runtime settings"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner)
    runtime.runtime_config_resolver = lambda _task: {"model": "local:test", "context_window": 65_536}
    task = runtime.submit("inspect safely", tmp_path, provider="ollama", max_attempts=1)
    completed = wait_for_state(runtime, task["id"])

    assert completed["state"] == "succeeded"
    assert received[0]["model"] == "local:test"
    assert received[0]["context_window"] == 65_536
    configured = [event for event in runtime.store.events(task["id"]) if event["event_type"] == "provider.configured"]
    assert configured[0]["payload"] == {"provider": "ollama", "model": "local:test", "context_window": 65_536}


def test_ollama_provider_uses_a_bounded_workspace_tool_loop(tmp_path: Path, monkeypatch):
    registry = ProviderRegistry()
    responses = iter([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {"name": "write_file", "arguments": {"path": "note.txt", "content": "ready\n"}},
        }]}},
        {"message": {"role": "assistant", "content": "Created note.txt and verified the focused change."}},
    ])
    requests: list[tuple[str, dict]] = []

    def fake_post(url, payload, headers=None, timeout=600):
        requests.append((url, payload))
        return next(responses)

    monkeypatch.setattr(registry, "_post_json", fake_post)
    emitted: list[tuple[str, dict]] = []
    result = registry.run(
        {"provider": "ollama", "workspace": str(tmp_path), "objective": "Create the focused note.", "model": "local:test", "context_window": 65_536},
        threading.Event(), lambda kind, payload: emitted.append((kind, payload)),
    )

    assert result == "Created note.txt and verified the focused change."
    assert (tmp_path / "note.txt").read_text(encoding="utf-8") == "ready\n"
    assert requests[0][0].endswith("/api/chat")
    assert requests[0][1]["tools"]
    assert "search_workspace" in {tool["function"]["name"] for tool in requests[0][1]["tools"]}
    assert "edit_file" in {tool["function"]["name"] for tool in requests[0][1]["tools"]}
    assert "pass its sha256" in requests[0][1]["messages"][0]["content"]
    assert requests[0][1]["options"] == {"num_ctx": 65_536}
    assert any(kind == "provider.started" and payload["context_window"] == 65_536 for kind, payload in emitted)
    tool_states = [payload["status"] for kind, payload in emitted if kind == "provider.tool" and payload["tool"] == "write_file"]
    assert tool_states == ["running", "succeeded"]
    assert any(kind == "provider.output" and payload["tool_steps"] == 1 for kind, payload in emitted)


def test_local_tool_lifecycle_redacts_sensitive_paths_before_execution(tmp_path: Path):
    registry = ProviderRegistry()
    payload = registry._workspace_tool_event_payload(
        "ollama", {"name": "read_file", "arguments": {"path": ".env"}}, "running",
    )

    assert payload["status"] == "running"
    assert payload["path"] == ""


def test_local_provider_refuses_to_claim_workspace_completion_without_a_tool(tmp_path: Path, monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setattr(registry, "_post_json", lambda *args, **kwargs: {
        "message": {"role": "assistant", "content": "Everything is complete."},
    })

    with pytest.raises(RuntimeError, match="without inspecting or acting"):
        registry.run(
            {"provider": "ollama", "workspace": str(tmp_path), "objective": "Inspect the project.", "model": "local:test"},
            threading.Event(), lambda *_args: None,
        )


def test_local_provider_refuses_completion_after_an_unresolved_tool_failure(tmp_path: Path, monkeypatch):
    registry = ProviderRegistry()
    responses = iter([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {"name": "not_a_workspace_tool", "arguments": {}},
        }]}},
        {"message": {"role": "assistant", "content": "Everything is complete."}},
    ])
    monkeypatch.setattr(registry, "_post_json", lambda *args, **kwargs: next(responses))

    with pytest.raises(RuntimeError, match="unresolved tool failure"):
        registry.run(
            {"provider": "ollama", "workspace": str(tmp_path), "objective": "Inspect the project.", "model": "local:test"},
            threading.Event(), lambda *_args: None,
        )


def test_openai_compatible_provider_replays_tool_results_with_call_ids(tmp_path: Path, monkeypatch):
    registry = ProviderRegistry()
    (tmp_path / "project.txt").write_text("workspace evidence", encoding="utf-8")
    responses = iter([
        {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [{
            "id": "call-123", "type": "function",
            "function": {"name": "read_file", "arguments": '{"path":"project.txt"}'},
        }]}}]},
        {"choices": [{"message": {"role": "assistant", "content": "Read project.txt and completed the requested review."}}]},
    ])
    payloads: list[dict] = []

    def fake_post(_url, payload, headers=None, timeout=600):
        payloads.append(payload)
        return next(responses)

    monkeypatch.setattr(registry, "_post_json", fake_post)
    monkeypatch.setenv("OBUS_OPENAI_COMPATIBLE_URL", "http://127.0.0.1:8000/v1")
    result = registry.run(
        {"provider": "openai-compatible", "workspace": str(tmp_path), "objective": "Review project.txt.", "model": "local:test"},
        threading.Event(), lambda *_args: None,
    )

    assert result.startswith("Read project.txt")
    tool_message = next(message for message in payloads[1]["messages"] if message["role"] == "tool")
    assert tool_message["tool_call_id"] == "call-123"
    assert "workspace evidence" in tool_message["content"]


def test_local_workspace_tools_protect_secrets_and_reject_shell_commands(tmp_path: Path):
    registry = ProviderRegistry()
    (tmp_path / ".env").write_text("TOKEN=not-for-models", encoding="utf-8")
    (tmp_path / "settings.py").write_text("API_KEY = 'not-for-models'\n", encoding="utf-8")

    with pytest.raises(ValueError, match="secret"):
        registry._execute_workspace_tool(tmp_path, "read_file", {"path": ".env"}, threading.Event())
    with pytest.raises(ValueError, match="secret-like content"):
        registry._execute_workspace_tool(tmp_path, "read_file", {"path": "settings.py"}, threading.Event())
    with pytest.raises(ValueError, match="secret-like content"):
        registry._execute_workspace_tool(
            tmp_path, "write_file", {"path": "new.py", "content": "TOKEN = 'not-for-models'\n"}, threading.Event(),
        )
    with pytest.raises(ValueError, match="only local test"):
        registry._execute_workspace_tool(tmp_path, "run_verification", {"command": "cmd /c dir"}, threading.Event())
    with pytest.raises(ValueError, match="shell syntax"):
        registry._execute_workspace_tool(tmp_path, "run_verification", {"command": "pytest -q && dir"}, threading.Event())
    with pytest.raises(ValueError, match="only local test"):
        registry._execute_workspace_tool(
            tmp_path, "run_verification", {"command": "git diff --no-index public.py C:\\outside\\private.txt"}, threading.Event(),
        )
    with pytest.raises(ValueError, match="only local test"):
        registry._execute_workspace_tool(tmp_path, "run_verification", {"command": "git diff --ext-diff"}, threading.Event())


@pytest.mark.parametrize(
    "command",
    [
        "ruff check src",
        "ruff format --check src",
        "black --check src",
        "mypy src",
        "pyright src",
        "pylint src",
        "eslint src",
        "prettier --check src/index.ts",
        "tsc --noEmit",
        "python -m ruff check src",
        "python -m black --check src",
    ],
)
def test_local_workspace_verification_allows_common_safe_quality_commands(command: str):
    assert ProviderRegistry._allowed_verification_command(command)


def test_local_workspace_verification_redacts_command_output(tmp_path: Path):
    registry = ProviderRegistry()
    (tmp_path / "test_safe_output.py").write_text(
        "import unittest\n\nclass SafeOutput(unittest.TestCase):\n    def test_output(self):\n        print('API_KEY=not-for-models')\n",
        encoding="utf-8",
    )

    result = registry._execute_workspace_tool(
        tmp_path, "run_verification", {"command": "python -m unittest -q", "timeout_seconds": 30}, threading.Event(),
    )

    assert result["ok"] is True
    assert "not-for-models" not in result["output"]
    assert "[REDACTED FIELD]" in result["output"]


def test_local_verification_receipt_event_is_bounded_and_redacted(tmp_path: Path, monkeypatch):
    registry = ProviderRegistry()
    (tmp_path / "test_safe_receipt.py").write_text(
        "import unittest\n\nclass SafeReceipt(unittest.TestCase):\n    def test_output(self):\n        print('API_KEY=not-for-receipts')\n",
        encoding="utf-8",
    )
    responses = iter([
        {"message": {"role": "assistant", "content": "", "tool_calls": [{
            "function": {"name": "run_verification", "arguments": {"command": "python -m unittest -q"}},
        }]}},
        {"message": {"role": "assistant", "content": "Verification completed safely."}},
    ])
    monkeypatch.setattr(registry, "_post_json", lambda *args, **kwargs: next(responses))
    emitted: list[tuple[str, dict]] = []

    result = registry.run(
        {"provider": "ollama", "workspace": str(tmp_path), "objective": "Verify the workspace.", "model": "local:test"},
        threading.Event(), lambda kind, payload: emitted.append((kind, payload)),
    )

    receipt = next(payload for kind, payload in emitted if kind == "provider.verification")
    assert result == "Verification completed safely."
    assert receipt["status"] == "passed"
    assert receipt["returncode"] == 0
    assert "not-for-receipts" not in receipt["output"]
    assert "[REDACTED FIELD]" in receipt["output"]
    assert len(receipt["output"]) <= 2_000


def test_local_workspace_search_is_bounded_literal_and_secret_safe(tmp_path: Path):
    registry = ProviderRegistry()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "public.py").write_text("needle = 1\nNEEDLE = 2\n", encoding="utf-8")
    (tmp_path / "src" / "settings.py").write_text("API_KEY = 'needle-but-secret'\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=needle-but-secret\n", encoding="utf-8")

    result = registry._execute_workspace_tool(
        tmp_path, "search_workspace", {"query": "needle", "max_results": 1}, threading.Event(),
    )

    assert result["ok"] is True
    assert result["truncated"] is True
    assert result["matches"] == [{"path": "src\\public.py", "line": 1, "text": "needle = 1"}]
    secret_scan = registry._execute_workspace_tool(
        tmp_path, "search_workspace", {"query": "not-present"}, threading.Event(),
    )
    assert secret_scan["matches"] == []
    assert secret_scan["skipped"] >= 2


def test_local_workspace_write_requires_fresh_read_fingerprint_and_is_atomic(tmp_path: Path):
    registry = ProviderRegistry()
    target = tmp_path / "public.py"
    target.write_text("value = 1\n", encoding="utf-8")
    before = registry._execute_workspace_tool(tmp_path, "read_file", {"path": "public.py"}, threading.Event())

    with pytest.raises(ValueError, match="changed; read it again"):
        registry._execute_workspace_tool(
            tmp_path, "write_file", {"path": "public.py", "content": "value = 2\n", "expected_sha256": "stale"}, threading.Event(),
        )
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    written = registry._execute_workspace_tool(
        tmp_path, "write_file", {"path": "public.py", "content": "value = 2\n", "expected_sha256": before["sha256"]}, threading.Event(),
    )
    after = registry._execute_workspace_tool(tmp_path, "read_file", {"path": "public.py"}, threading.Event())

    assert written == {"ok": True, "path": "public.py", "bytes": 10, "created": False}
    assert after["content"] == "value = 2\n"
    assert after["sha256"] != before["sha256"]
    assert not list(tmp_path.glob(".public.py.obus-*.tmp"))


def test_local_workspace_edit_is_exact_checksum_guarded_and_atomic(tmp_path: Path):
    registry = ProviderRegistry()
    target = tmp_path / "public.py"
    target.write_text("first = 1\nsecond = 1\n", encoding="utf-8")
    before = registry._execute_workspace_tool(tmp_path, "read_file", {"path": "public.py"}, threading.Event())

    with pytest.raises(ValueError, match="multiple locations"):
        registry._execute_workspace_tool(
            tmp_path, "edit_file", {
                "path": "public.py", "old_text": " = 1", "new_text": " = 2",
                "expected_sha256": before["sha256"],
            }, threading.Event(),
        )
    with pytest.raises(ValueError, match="changed; read it again"):
        registry._execute_workspace_tool(
            tmp_path, "edit_file", {
                "path": "public.py", "old_text": "first = 1", "new_text": "first = 2",
                "expected_sha256": "stale",
            }, threading.Event(),
        )

    edited = registry._execute_workspace_tool(
        tmp_path, "edit_file", {
            "path": "public.py", "old_text": "first = 1", "new_text": "first = 2",
            "expected_sha256": before["sha256"],
        }, threading.Event(),
    )
    after = registry._execute_workspace_tool(tmp_path, "read_file", {"path": "public.py"}, threading.Event())

    assert edited["ok"] is True
    assert edited["replacements"] == 1
    assert "-first = 1" in edited["diff"]
    assert "+first = 2" in edited["diff"]
    assert after["content"] == before["content"].replace("first = 1", "first = 2", 1)
    assert after["sha256"] == edited["sha256"]
    assert not list(tmp_path.glob(".public.py.obus-*.tmp"))

    duplicate = tmp_path / "duplicate.txt"
    duplicate.write_text("item = 1\nitem = 1\n", encoding="utf-8")
    duplicate_before = registry._execute_workspace_tool(tmp_path, "read_file", {"path": "duplicate.txt"}, threading.Event())
    with pytest.raises(ValueError, match="must be a boolean"):
        registry._execute_workspace_tool(
            tmp_path, "edit_file", {
                "path": "duplicate.txt", "old_text": "item = 1", "new_text": "item = 2",
                "expected_sha256": duplicate_before["sha256"], "replace_all": "true",
            }, threading.Event(),
        )
    bulk = registry._execute_workspace_tool(
        tmp_path, "edit_file", {
            "path": "duplicate.txt", "old_text": "item = 1", "new_text": "item = 2",
            "expected_sha256": duplicate_before["sha256"], "replace_all": True,
        }, threading.Event(),
    )
    assert bulk["replacements"] == 2
    assert duplicate.read_text(encoding="utf-8") == "item = 2\nitem = 2\n"


def test_durable_queue_prioritizes_urgent_work_and_keeps_fifo_within_a_priority(tmp_path: Path):
    store = HarnessStore(tmp_path / "harness.sqlite3")
    low = store.create_task("background research", tmp_path, "local", 10, 1)
    first_urgent = store.create_task("interactive repair", tmp_path, "local", 90, 1)
    second_urgent = store.create_task("interactive verification", tmp_path, "local", 90, 1)

    queued = store.list_queued_tasks()

    assert [task["id"] for task in queued] == [first_urgent["id"], second_urgent["id"], low["id"]]


def test_worker_drains_urgent_queued_work_before_lower_priority_work(tmp_path: Path):
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    completed_objectives: list[str] = []

    def runner(task, _cancellation, _emit):
        if task["objective"] == "blocker":
            blocker_started.set()
            assert release_blocker.wait(2)
        else:
            completed_objectives.append(task["objective"])
        return "done"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner, max_workers=1)
    blocker = runtime.submit("blocker", tmp_path, priority=50)
    assert blocker_started.wait(2)
    low = runtime.submit("background research", tmp_path, priority=10)
    urgent = runtime.submit("interactive repair", tmp_path, priority=90)

    release_blocker.set()
    assert wait_for_state(runtime, blocker["id"])['state'] == "succeeded"
    assert wait_for_state(runtime, urgent["id"])['state'] == "succeeded"
    assert wait_for_state(runtime, low["id"])['state'] == "succeeded"
    assert completed_objectives == ["interactive repair", "background research"]


def test_harness_repairs_after_failure_and_drains_queue(tmp_path: Path):
    attempts: dict[str, int] = {}

    def repairing_runner(task, cancellation, emit):
        attempts[task["id"]] = attempts.get(task["id"], 0) + 1
        if attempts[task["id"]] == 1:
            raise RuntimeError("injected failure")
        return "repaired"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=repairing_runner, max_workers=1)
    first = runtime.submit("first", tmp_path)
    second = runtime.submit("second", tmp_path)
    assert wait_for_state(runtime, first["id"], timeout=8)["state"] == "succeeded"
    assert wait_for_state(runtime, second["id"], timeout=8)["state"] == "succeeded"
    assert attempts[first["id"]] == 2
    assert attempts[second["id"]] == 2


def test_harness_rolls_back_when_independent_workspace_verification_fails(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "source.txt"
    target.write_text("before", encoding="utf-8")

    def runner(task, cancellation, emit):
        target.write_text("trailing whitespace   \n", encoding="utf-8")
        return "agent claimed success"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner)
    runtime.recovery.verify_workspace = lambda checkpoint_id: {
        "checkpoint_id": checkpoint_id, "kind": "checkpoint-diff-check", "read_only": True,
        "status": "failed", "reason": "Checkpoint diff contains trailing whitespace introduced by this task.", "checks": [],
    }
    task = runtime.submit("make a change", workspace, max_attempts=1)
    completed = wait_for_state(runtime, task["id"])

    assert completed["state"] == "failed"
    assert target.read_text(encoding="utf-8") == "before"
    verification_events = [event for event in runtime.store.events(task["id"]) if event["event_type"] == "workspace.verified"]
    assert verification_events[0]["payload"]["status"] == "failed"
    workflow_events = [event["payload"] for event in runtime.store.events(task["id"])
                       if event["event_type"] == "workflow.stage"]
    assert workflow_events[-1]["stage"] == "verify"
    assert workflow_events[-1]["status"] == "failed"


def test_harness_cancellation_stops_running_task(tmp_path: Path):
    started = threading.Event()

    def blocking_runner(task, cancellation, emit):
        started.set()
        while not cancellation.wait(0.01):
            pass
        raise InterruptedError("task cancelled")

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=blocking_runner)
    task = runtime.submit("wait", tmp_path)
    assert started.wait(2)
    runtime.cancel(task["id"])
    assert wait_for_state(runtime, task["id"])["state"] == "cancelled"
    stages = [event["payload"] for event in runtime.store.events(task["id"])
              if event["event_type"] == "workflow.stage"]
    assert stages[-1]["stage"] == "work"
    assert stages[-1]["status"] == "cancelled"


def test_store_marks_unfinished_tasks_interrupted_without_replay(tmp_path: Path):
    database = tmp_path / "harness.sqlite3"
    store = HarnessStore(database)
    task = store.create_task("resume", tmp_path, "local", 50, 3)
    store.transition(task["id"], "running", started_at="now")
    recovered = HarnessStore(database).get_task(task["id"])
    assert recovered["state"] == "interrupted"
    assert "restart" in recovered["error"].lower()
    assert any(event["event_type"] == "task.interrupted" for event in HarnessStore(database).events(task["id"]))


def test_harness_resumes_interrupted_ordinary_task_with_safe_reinspection(tmp_path: Path):
    received: list[dict] = []
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda task, _cancel, _emit: received.append(task) or "done")
    task = runtime.store.create_task("inspect the current workspace", tmp_path, "local", 50, 1)
    runtime.store.transition(task["id"], "interrupted", error="restart")

    resumed = runtime.resume(task["id"])

    assert wait_for_state(runtime, task["id"])["state"] == "succeeded"
    assert resumed["id"] == task["id"]
    assert received[0]["resumed_after_interruption"] is True
    assert any(event["event_type"] == "task.resume_requested" for event in runtime.store.events(task["id"]))


def test_store_keeps_terminal_task_and_redacted_receipts_after_restart(tmp_path: Path):
    database = tmp_path / "harness.sqlite3"
    store = HarnessStore(database)
    task = store.create_task("remember completed work", tmp_path, "local", 50, 1)
    store.add_event(task["id"], "provider.verification", {
        "provider": "ollama", "status": "passed", "ok": True, "returncode": 0, "output": "Listing '.'...",
    })
    store.transition(task["id"], "succeeded", result="Finished without replaying the task.", finished_at="now")

    reopened = HarnessStore(database)
    restored = reopened.list_tasks(limit=1)
    events = reopened.events(task["id"])

    assert restored[0]["id"] == task["id"]
    assert restored[0]["state"] == "succeeded"
    assert restored[0]["result"] == "Finished without replaying the task."
    assert any(event["event_type"] == "provider.verification" for event in events)


def test_desktop_timeline_subscribes_to_and_labels_workflow_stages():
    runtime_source = TestClient(__import__("backend.main", fromlist=["app"]).app).get("/static/aui/runtime.js").text

    assert 'event.event_type === "workflow.stage"' in runtime_source
    assert "Workflow · ${payload.stage || \"stage\"} · ${payload.status || \"recorded\"}." in runtime_source
    assert '"workflow.stage"' in runtime_source


def test_harness_http_contracts_use_durable_runtime(tmp_path: Path, monkeypatch):
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda task, cancel, emit: "done")
    monkeypatch.setattr(harness_api, "runtime", runtime)
    app = FastAPI()
    app.include_router(harness_api.router)
    client = TestClient(app)

    health = client.get("/api/harness/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "guarded-autonomous"
    response = client.post("/api/harness/tasks", json={"objective": "complete task", "workspace": str(tmp_path)})
    assert response.status_code == 202
    task_id = response.json()["id"]
    assert wait_for_state(runtime, task_id)["state"] == "succeeded"
    assert client.get(f"/api/harness/tasks/{task_id}/events").json()["events"]
    capabilities = client.get("/api/harness/capabilities").json()
    assert capabilities["approval_required"] == "major-destructive-or-hardware-risk"
    assert capabilities["remote_authority"] == "workspace-guarded"
    assert "codex.auto-review" in capabilities["capabilities"]
    assert "local-model.workspace-tool-loop" in capabilities["capabilities"]
    assert "workflow.inspect-work-verify" in capabilities["capabilities"]
    assert "codex.unrestricted" not in capabilities["capabilities"]

    blocked = client.post(
        "/api/harness/tasks",
        json={"objective": "recursively delete the entire backup history", "workspace": str(tmp_path)},
    )
    assert blocked.status_code == 409
    approval_id = blocked.json()["detail"]["approval_id"]
    assert "bulk_or_irrecoverable_deletion" in blocked.json()["detail"]["risks"]
    approval = client.get("/api/harness/approvals").json()["approvals"][0]
    assert approval["id"] == approval_id
    assert approval["status"] == "pending"
    assert "recursively delete" in approval["objective_preview"]
    approved = client.post(f"/api/harness/approvals/{approval_id}/approve", json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    started = client.post(
        "/api/harness/tasks",
        json={"objective": "recursively delete the entire backup history", "workspace": str(tmp_path), "approval_id": approval_id},
    )
    assert started.status_code == 202
    approved_task_id = started.json()["id"]
    assert wait_for_state(runtime, approved_task_id)["state"] == "succeeded"
    events = client.get(f"/api/harness/tasks/{approved_task_id}/events").json()["events"]
    assert any(event["event_type"] == "approval.consumed" for event in events)
    reused = client.post(
        "/api/harness/tasks",
        json={"objective": "recursively delete the entire backup history", "workspace": str(tmp_path), "approval_id": approval_id},
    )
    assert reused.status_code == 409
    assert "consumed" in reused.json()["detail"]


def test_harness_resume_http_contract_requires_local_ordinary_interrupted_task(tmp_path: Path, monkeypatch):
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda task, _cancel, _emit: "done")
    monkeypatch.setattr(harness_api, "runtime", runtime)
    app = FastAPI()
    app.include_router(harness_api.router)
    client = TestClient(app)
    ordinary = runtime.store.create_task("inspect the current workspace", tmp_path, "local", 50, 1)
    runtime.store.transition(ordinary["id"], "interrupted", error="restart")
    resumed = client.post(f"/api/harness/tasks/{ordinary['id']}/resume")
    assert resumed.status_code == 202
    assert wait_for_state(runtime, ordinary["id"])["state"] == "succeeded"

    monkeypatch.setattr(runtime, "_start", lambda *_args, **_kwargs: None)
    risky = runtime.store.create_task("raise the GPU power limit", tmp_path, "local", 50, 1)
    runtime.store.transition(risky["id"], "interrupted", error="restart")
    blocked = client.post(f"/api/harness/tasks/{risky['id']}/resume")
    assert blocked.status_code == 409
    assert "never resumed" in blocked.json()["detail"]["message"]


def test_harness_approval_record_is_redacted_and_bound_to_exact_task_configuration(tmp_path: Path):
    store = HarnessStore(tmp_path / "harness.sqlite3")
    objective = "raise the GPU power limit using API_KEY=super-secret-key"
    approval = store.ensure_approval(objective, tmp_path, ["hardware_safety_controls"], "codex", None, 50, 3)
    assert approval["status"] == "pending"
    assert "super-secret-key" not in approval["objective_preview"]
    assert "REDACTED" in approval["objective_preview"]
    store.decide_approval(approval["id"], "approved")
    with pytest.raises(ValueError, match="does not match"):
        store.consume_approval(approval["id"], objective, tmp_path, ["hardware_safety_controls"], "codex", None, 51, 3)
    consumed = store.consume_approval(approval["id"], objective, tmp_path, ["hardware_safety_controls"], "codex", None, 50, 3)
    assert consumed["status"] == "consumed"


def test_harness_http_requires_existing_workspace_and_redacts_task_surfaces(tmp_path: Path, monkeypatch):
    def runner(task, cancellation, emit):
        emit("tool.output", {"token": "super-secret-token", "text": "API_KEY=super-secret-key"})
        return "Completed with API_KEY=super-secret-key and token super-secret-token"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner)
    monkeypatch.setattr(harness_api, "runtime", runtime)
    app = FastAPI()
    app.include_router(harness_api.router)
    client = TestClient(app)

    missing = client.post("/api/harness/tasks", json={"objective": "inspect", "workspace": str(tmp_path / "not-created")})
    assert missing.status_code == 400
    response = client.post("/api/harness/tasks", json={"objective": "inspect API_KEY=super-secret-key", "workspace": str(tmp_path)})
    assert response.status_code == 202
    task_id = response.json()["id"]
    assert wait_for_state(runtime, task_id)["state"] == "succeeded"

    task = client.get(f"/api/harness/tasks/{task_id}").json()
    events = client.get(f"/api/harness/tasks/{task_id}/events").json()["events"]
    serialized = repr({"task": task, "events": events})
    assert "super-secret" not in serialized
    assert "REDACTED" in serialized


def test_harness_change_review_api_binds_diff_to_task_checkpoint(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "app.py"
    target.write_text("print('before')\n", encoding="utf-8")

    def runner(task, cancellation, emit):
        target.write_text("print('after')\n", encoding="utf-8")
        (workspace / "new.py").write_text("print('new')\n", encoding="utf-8")
        return "changed two safe files"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner)
    monkeypatch.setattr(harness_api, "runtime", runtime)
    app = FastAPI()
    app.include_router(harness_api.router)
    client = TestClient(app)
    queued = runtime.store.create_task("queued", workspace, "local", 50, 1)
    no_checkpoint = client.get(f"/api/harness/tasks/{queued['id']}/changes")
    assert no_checkpoint.status_code == 200
    assert no_checkpoint.json()["checkpoint"] is None
    created = client.post("/api/harness/tasks", json={"objective": "make a safe change", "workspace": str(workspace)})
    assert created.status_code == 202
    task_id = created.json()["id"]
    assert wait_for_state(runtime, task_id)["state"] == "succeeded"

    summary = client.get(f"/api/harness/tasks/{task_id}/changes")
    assert summary.status_code == 200
    paths = {item["path"]: item for item in summary.json()["changes"]}
    assert paths["app.py"]["status"] == "modified"
    assert paths["new.py"]["status"] == "added"
    assert summary.json()["read_only"] is True
    diff = client.get(f"/api/harness/tasks/{task_id}/changes/app.py")
    assert diff.status_code == 200
    assert "-print('before')" in diff.json()["diff"]
    assert "+print('after')" in diff.json()["diff"]
