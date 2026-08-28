"""Regression coverage for persistent-agent provider readiness selection."""

from __future__ import annotations

import pytest

from backend.persistent_agents import select_persistent_agent_key


def _key(*, local: bool, verified: bool = True) -> dict[str, object]:
    return {
        "id": "key-local-ollama" if local else "key-remote",
        "state": "ready",
        "local": local,
        "verified": verified,
        "capabilities": [],
        "max_context_tokens": 131_072,
    }


def test_manual_verified_local_key_survives_transient_probe_contention() -> None:
    key = _key(local=True)

    selected = select_persistent_agent_key(
        {}, "inspect the workspace", {"keys": [key]},
        {"key-local-ollama": {"connected": False}}, {},
        manual_key_id="key-local-ollama",
    )

    assert selected is key


def test_manual_remote_key_still_requires_a_live_connection() -> None:
    key = _key(local=False)

    with pytest.raises(RuntimeError, match="not ready and connected"):
        select_persistent_agent_key(
            {}, "inspect the workspace", {"keys": [key]},
            {"key-remote": {"connected": False}}, {},
            manual_key_id="key-remote",
        )
