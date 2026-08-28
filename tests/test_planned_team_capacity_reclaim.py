"""Regression coverage for disposable planned-team worker reclamation."""

from __future__ import annotations

from backend import main


def test_completed_planned_team_workers_are_archived_after_ledger_synthesis(monkeypatch) -> None:
    ledger_id = "task-complete"
    state = {
        "task_ledgers": [{"id": ledger_id, "kind": "planned-team", "findings": []}],
        "persistent_agents": [
            {"id": "agent-complete", "status": "complete", "task_ledger_id": ledger_id},
            {"id": "agent-failed", "status": "failed", "task_ledger_id": ledger_id},
            {"id": "agent-user", "status": "idle", "task_ledger_id": "user-agent"},
        ],
    }
    saved: list[dict] = []

    monkeypatch.setattr(main, "load_state", lambda: state)
    monkeypatch.setattr(main, "save_state", lambda value: saved.append(value))
    monkeypatch.setattr(main, "_runtime_event", lambda *args, **kwargs: None)
    main.PERSISTENT_AGENT_THREADS.clear()

    main._synthesize_task_ledger(ledger_id, ["agent-complete", "agent-failed"])

    ledger = state["task_ledgers"][0]
    assert ledger["status"] == "partial"
    assert ledger["agent_statuses"] == {"agent-complete": "complete", "agent-failed": "failed"}
    assert state["persistent_agents"][0]["status"] == "deleted"
    assert state["persistent_agents"][1]["status"] == "deleted"
    assert state["persistent_agents"][2]["status"] == "idle"
    assert saved == [state]
