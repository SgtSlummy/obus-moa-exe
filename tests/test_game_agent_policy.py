"""Focused policy-boundary tests for the private game agent."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.game_agent import Job, run_job


def _job(**policy_overrides):
    policy = {
        "mode": "local-free",
        "namespace": "campaign-1",
        "tools": False,
        "personal_memory": False,
        "auto_memory": False,
        **policy_overrides,
    }
    return Job.model_validate(
        {
            "contract": "raph-obus-game-v1",
            "scope": {"campaign": "campaign-1", "owner": "host-1", "role": "host"},
            "session": "session-1",
            "requestId": "request-1",
            "task": "narration",
            "instructions": "Narrate only from supplied evidence.",
            "evidence": {"question": "What happens next?"},
            "policy": policy,
            "max_tokens": 64,
        }
    )


def test_codex_policy_rejects_before_any_provider_or_fallback_dispatch():
    calls: list[str] = []

    def catalogue():
        calls.append("catalogue")
        return []

    def local(*_args):
        calls.append("local")
        return "unexpected"

    def remote(*_args):
        calls.append("remote")
        return "unexpected"

    with pytest.raises(HTTPException) as raised:
        run_job(_job(codex=True), get_keys=catalogue, local=local, remote=remote)

    assert raised.value.status_code == 409
    assert "Codex escalation is not supported" in str(raised.value.detail)
    assert calls == []


def test_escalation_eligible_task_runs_locally_without_free_or_codex_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.game_agent.ROOT", tmp_path)
    calls: list[str] = []
    local_key = {
        "id": "key-local-ollama",
        "provider": "ollama",
        "connected": True,
        "verified": True,
        "base_url": "http://127.0.0.1:11434",
        "model": "test-local",
    }

    def local(key, _prompt, _maximum):
        calls.append(f"local:{key['model']}")
        return "A safe local answer."

    def remote(*_args):
        calls.append("remote")
        raise AssertionError("A local success must not fall back to a remote provider")

    result = run_job(
        _job(escalationEligible=True),
        get_keys=lambda: [local_key],
        local=local,
        remote=remote,
    )

    assert result["text"] == "A safe local answer."
    assert result["trace"] == [
        {
            "provider": "key-local-ollama",
            "model": "test-local",
            "destination": "local",
            "cost": "local",
            "attempt": 1,
            "status": "ready",
        }
    ]
    assert calls == ["local:test-local"]


def test_capabilities_distinguish_generic_remote_routes_from_verified_free_fallback():
    from backend.game_agent import capabilities

    declared = capabilities()

    assert declared["generic_remote_routes"] is False
    assert declared["verified_free_route_fallback"] is True
    assert "zero-cost" in declared["free_route_policy"]
    assert declared["codex_available"] is False
