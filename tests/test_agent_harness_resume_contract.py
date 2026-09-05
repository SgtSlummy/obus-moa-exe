from __future__ import annotations

import threading
from pathlib import Path

from backend.agent_harness import AgentHarnessRuntime


def test_resumed_execution_marks_runner_task_and_records_safe_reinspection(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    observed: dict[str, object] = {}

    def runner(task: dict[str, object], _cancellation: threading.Event, _emit: object) -> str:
        observed["task"] = task
        return "safe reinspection verified"

    runtime = AgentHarnessRuntime(tmp_path / "harness.sqlite", runner=runner, max_workers=1)
    task = runtime.store.create_task(
        objective="Resume a verified local task",
        workspace=workspace,
        source="test",
        priority=50,
        max_attempts=1,
    )

    runtime._execute(task["id"], threading.Event(), resumed=True)

    runtime_task = observed["task"]
    assert isinstance(runtime_task, dict)
    assert runtime_task["resumed_after_interruption"] is True
    assert runtime.store.get_task(task["id"])["state"] == "succeeded"
    assert any(
        event["event_type"] == "task.resumed"
        and event["payload"] == {"explicit": True, "safe_reinspection": True}
        for event in runtime.store.events(task["id"])
    )
