"""Dashboard provider rendering should not repeat a fresh Ollama probe."""

from __future__ import annotations

from backend import main


def test_provider_statuses_uses_supplied_ollama_snapshot(monkeypatch) -> None:
    def unexpected_probe() -> dict:
        raise AssertionError("provider rendering must reuse the dashboard snapshot")

    monkeypatch.setattr(main, "get_ollama_status", unexpected_probe)
    snapshot = {
        "connected": True,
        "models": ["gpt-oss:20b"],
        "model_contexts": {"gpt-oss:20b": 117_964},
        "runtime_contexts": {"gpt-oss:20b": 117_964},
    }
    providers = main.provider_statuses({"keys": [main.DEFAULT_KEYS[0]]}, snapshot)

    assert providers[0]["connected"] is True
    assert providers[0]["max_context_tokens"] == 117_964
