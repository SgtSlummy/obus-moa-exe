from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent_harness import AgentHarnessRuntime, HarnessStore
from backend import autonomy_api
from backend.autonomy import ObjectiveScheduler, ProviderRegistry


def test_harness_migrates_existing_database_and_preserves_codex_default(tmp_path: Path) -> None:
    database = tmp_path / "harness.sqlite3"
    store = HarnessStore(database)
    first = store.create_task("before migration", tmp_path, "test", 50, 1)
    runtime = AgentHarnessRuntime(database, runner=lambda task, cancellation, emit: "done", max_workers=1)
    migrated = runtime.store.get_task(first["id"])
    assert migrated["provider"] == "codex"
    assert migrated["model"] is None


def test_runtime_accepts_explicit_local_provider_with_fake_runner(tmp_path: Path) -> None:
    seen: list[dict[str, Any]] = []

    def runner(task, cancellation, emit):
        seen.append(task)
        return "local result"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=runner, max_workers=1)
    task = runtime.submit("use local model", tmp_path, provider="ollama", model="qwen-test")
    thread = runtime._threads[task["id"]]
    thread.join(timeout=5)
    completed = runtime.store.get_task(task["id"])
    assert completed["state"] == "succeeded"
    assert completed["provider"] == "ollama"
    assert completed["model"] == "qwen-test"
    assert seen[0]["provider"] == "ollama"


def test_provider_discovery_reports_codex_and_ollama(monkeypatch) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"models": [{"name": "qwen2.5"}]}).encode()

    monkeypatch.setattr("backend.autonomy.shutil.which", lambda command: "/usr/bin/codex")
    monkeypatch.setattr("backend.autonomy.urllib.request.urlopen", lambda request, timeout=0: Response())
    providers = ProviderRegistry().capabilities()
    assert providers["default"] == "codex"
    assert providers["available"] == ["codex", "ollama"]
    assert providers["providers"][1]["models"] == ["qwen2.5"]


def test_objective_scheduler_persists_and_submits_due_objective(tmp_path: Path) -> None:
    submitted: list[dict[str, Any]] = []

    def submit(objective, workspace, **kwargs):
        submitted.append({"objective": objective, "workspace": workspace, **kwargs})
        return {"id": "scheduled-task"}

    scheduler = ObjectiveScheduler(tmp_path / "scheduler.sqlite3", submit)
    item = scheduler.create("repair", "inspect and repair", tmp_path, 60, provider="codex", priority=80)
    assert scheduler.run_due(now=item["next_run_at"] - 1) == []
    assert scheduler.run_due(now=item["next_run_at"] + 1) == ["scheduled-task"]
    updated = scheduler.get(item["id"])
    assert updated["last_task_id"] == "scheduled-task"
    assert submitted[0]["source"] == "scheduler"
    assert submitted[0]["priority"] == 80


def test_objective_scheduler_can_disable_and_delete(tmp_path: Path) -> None:
    scheduler = ObjectiveScheduler(tmp_path / "scheduler.sqlite3", lambda *args, **kwargs: {"id": "task"})
    item = scheduler.create("maintenance", "maintain", tmp_path, 1)
    assert scheduler.set_enabled(item["id"], False)["enabled"] is False
    assert scheduler.run_due(now=item["next_run_at"] + 10) == []
    scheduler.delete(item["id"])
    assert scheduler.list() == []


def test_objective_scheduler_skips_overlap_and_disables_major_risk_work(tmp_path: Path) -> None:
    submitted: list[str] = []

    def submit(objective, workspace, **kwargs):
        submitted.append(objective)
        return {"id": "active-task"}

    scheduler = ObjectiveScheduler(tmp_path / "scheduler.sqlite3", submit, task_active=lambda task_id: task_id == "active-task")
    ordinary = scheduler.create("ordinary", "inspect the project", tmp_path, 60)
    assert scheduler.run_due(now=ordinary["next_run_at"] + 1) == ["active-task"]
    launched = scheduler.get(ordinary["id"])
    assert scheduler.run_due(now=launched["next_run_at"] + 1) == []
    skipped = scheduler.get(ordinary["id"])
    assert submitted == ["inspect the project"]
    assert skipped["enabled"] is True
    assert "still active" in skipped["last_error"]

    risky = scheduler.create("danger", "format the entire disk", tmp_path, 60)
    assert scheduler.run_due(now=risky["next_run_at"] + 1) == []
    rejected = scheduler.get(risky["id"])
    assert rejected["enabled"] is False
    assert "major-risk" in rejected["last_error"]


def test_objective_http_contract_requires_existing_workspace_and_rejects_risky_schedule(tmp_path: Path, monkeypatch) -> None:
    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite3", runner=lambda task, cancellation, emit: "done")
    scheduler = ObjectiveScheduler(tmp_path / "scheduler.sqlite3", runtime.submit)
    monkeypatch.setattr(autonomy_api, "runtime", runtime)
    monkeypatch.setattr(autonomy_api, "objective_scheduler", scheduler)
    app = FastAPI()
    app.include_router(autonomy_api.router)
    client = TestClient(app)

    created = client.post("/api/harness/objectives", json={
        "name": "ordinary", "objective": "inspect the project", "workspace": str(tmp_path),
        "interval_seconds": 1800, "provider": "codex",
    })
    assert created.status_code == 201
    objective_id = created.json()["id"]
    assert client.get("/api/harness/objectives").json()["objectives"][0]["id"] == objective_id
    assert client.patch(f"/api/harness/objectives/{objective_id}", json={"enabled": False}).json()["enabled"] is False
    assert client.post("/api/harness/objectives", json={
        "name": "danger", "objective": "clear the disk partition table", "workspace": str(tmp_path),
        "interval_seconds": 1800,
    }).status_code == 409
    assert client.post("/api/harness/objectives", json={
        "name": "missing", "objective": "inspect", "workspace": str(tmp_path / "not-created"),
        "interval_seconds": 1800,
    }).status_code == 400
    assert client.delete(f"/api/harness/objectives/{objective_id}").status_code == 204
