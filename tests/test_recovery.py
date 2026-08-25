from __future__ import annotations

from pathlib import Path

from backend.agent_harness import AgentHarnessRuntime
from backend.recovery import RecoveryManager


def test_checkpoint_restores_changed_files_and_removes_new_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    original = workspace / "config.txt"
    original.write_text("before", encoding="utf-8")
    manager = RecoveryManager(tmp_path / "state" / "harness.sqlite3")
    checkpoint = manager.create("task-1", workspace)
    original.write_text("after", encoding="utf-8")
    created = workspace / "created.txt"
    created.write_text("agent-created", encoding="utf-8")
    receipt = manager.rollback(checkpoint["id"])
    assert receipt["disposition"] == "rolled_back"
    assert original.read_text(encoding="utf-8") == "before"
    assert not created.exists()
    assert "config.txt" in receipt["restored"]
    assert "created.txt" in receipt["removed"]


def test_checkpoint_commit_is_idempotent_and_does_not_rollback(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "result.txt"
    target.write_text("before", encoding="utf-8")
    manager = RecoveryManager(tmp_path / "state" / "harness.sqlite3")
    checkpoint = manager.create("task-2", workspace)
    target.write_text("successful", encoding="utf-8")
    manager.complete(checkpoint["id"])
    receipt = manager.rollback(checkpoint["id"])
    assert receipt["disposition"] == "committed"
    assert target.read_text(encoding="utf-8") == "successful"


def test_checkpoint_skips_oversized_files_without_destroying_them(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    large = workspace / "large.bin"
    large.write_bytes(b"12345")
    manager = RecoveryManager(tmp_path / "state" / "harness.sqlite3", max_file_bytes=4)
    checkpoint = manager.create("task-3", workspace)
    assert checkpoint["files_skipped"] == 1
    large.write_bytes(b"changed")
    receipt = manager.rollback(checkpoint["id"])
    assert receipt["disposition"] == "rolled_back"
    assert large.read_bytes() == b"changed"


def test_failure_fingerprint_opens_circuit_after_three_matches(tmp_path: Path) -> None:
    manager = RecoveryManager(tmp_path / "state" / "harness.sqlite3")
    failure = RuntimeError("same deterministic failure")
    assert manager.record_failure("one", failure)["circuit_open"] is False
    assert manager.record_failure("two", failure)["circuit_open"] is False
    third = manager.record_failure("three", failure)
    assert third["circuit_open"] is True
    assert manager.circuit_open(third["fingerprint"])


def test_runtime_rolls_back_failed_attempt_before_repair(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "source.txt"
    target.write_text("baseline", encoding="utf-8")
    attempts = 0

    def runner(task, cancellation, emit):
        nonlocal attempts
        attempts += 1
        path = Path(task["workspace"]) / "source.txt"
        if attempts == 1:
            path.write_text("broken", encoding="utf-8")
            (Path(task["workspace"]) / "junk.txt").write_text("junk", encoding="utf-8")
            raise RuntimeError("repairable")
        assert path.read_text(encoding="utf-8") == "baseline"
        assert not (Path(task["workspace"]) / "junk.txt").exists()
        path.write_text("fixed", encoding="utf-8")
        return "verified"

    runtime = AgentHarnessRuntime(tmp_path / "state" / "harness.sqlite3", runner=runner, max_workers=1)
    task = runtime.submit("repair workspace", workspace, max_attempts=2)
    runtime._threads[task["id"]].join(timeout=10)
    completed = runtime.store.get_task(task["id"])
    assert completed["state"] == "succeeded"
    assert target.read_text(encoding="utf-8") == "fixed"
    checkpoints = runtime.recovery.list(task["id"])
    assert {checkpoint["status"] for checkpoint in checkpoints} == {"rolled_back", "committed"}
