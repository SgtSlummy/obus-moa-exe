from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from backend.agent_harness import AgentHarnessRuntime, HarnessStore
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
