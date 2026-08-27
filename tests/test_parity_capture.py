from backend.parity_capture import task_evidence


def test_task_evidence_is_redacted_and_never_replays():
    result = task_evidence({"id": "task-1", "state": "succeeded", "provider": "codex", "objective": "use API_KEY=secret", "result": "done"})
    assert result["replay"] == "none"
    assert result["verifier"]["required"] is True
    assert "secret" not in result["evidence"]["objective_preview"]
