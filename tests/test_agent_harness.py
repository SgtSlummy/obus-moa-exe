import threading
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent_harness import AgentHarnessRuntime, HarnessStore
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
    assert "lesson.promoted" in event_types
    lessons = runtime.store.lessons()
    assert lessons[0]["task_id"] == task["id"]
    assert lessons[0]["active"] is True


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


def test_store_recovers_interrupted_tasks_to_queue(tmp_path: Path):
    database = tmp_path / "harness.sqlite3"
    store = HarnessStore(database)
    task = store.create_task("resume", tmp_path, "local", 50, 3)
    store.transition(task["id"], "running", started_at="now")
    recovered = HarnessStore(database).get_task(task["id"])
    assert recovered["state"] == "queued"


def test_harness_http_contracts_use_durable_runtime(tmp_path: Path, monkeypatch):
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda task, cancel, emit: "done")
    monkeypatch.setattr(harness_api, "runtime", runtime)
    app = FastAPI()
    app.include_router(harness_api.router)
    client = TestClient(app)

    health = client.get("/api/harness/health")
    assert health.status_code == 200
    assert health.json()["mode"] == "unrestricted"
    response = client.post("/api/harness/tasks", json={"objective": "complete task", "workspace": str(tmp_path)})
    assert response.status_code == 202
    task_id = response.json()["id"]
    assert wait_for_state(runtime, task_id)["state"] == "succeeded"
    assert client.get(f"/api/harness/tasks/{task_id}/events").json()["events"]
    capabilities = client.get("/api/harness/capabilities").json()
    assert capabilities["approval_required"] is False
    assert capabilities["remote_authority"] == "full"
