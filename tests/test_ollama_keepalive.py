from __future__ import annotations

import threading
from types import SimpleNamespace

from backend import autonomy, improvement_baseline


def test_provider_ollama_chat_keeps_model_resident_and_context(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.delenv("OBUS_OLLAMA_URL", raising=False)
    registry = object.__new__(autonomy.ProviderRegistry)

    def fake_post_json(_self, url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"message": {"content": "ok"}}

    monkeypatch.setattr(
        autonomy,
        "guard_epistemic_request",
        lambda _objective: SimpleNamespace(blocked=False, response=None),
    )
    monkeypatch.setattr(autonomy, "epistemic_policy", lambda: "")
    monkeypatch.setattr(
        autonomy.ProviderRegistry,
        "_ollama_messages",
        lambda _self, messages: [{"role": "system", "content": "system"}, *messages],
    )
    monkeypatch.setattr(autonomy.ProviderRegistry, "_workspace_tools", lambda _self: [])
    monkeypatch.setattr(autonomy.ProviderRegistry, "_post_json", fake_post_json)
    monkeypatch.setattr(
        autonomy.ProviderRegistry,
        "_run_workspace_tool_loop",
        lambda _self, _task, _cancellation, _emit, _provider, _model, request: request(
            [{"role": "user", "content": "probe"}]
        )["content"],
    )

    result = registry._run_ollama(
        {
            "objective": "verify residency",
            "model": "fixture-model",
            "context_window": 262_144,
        },
        threading.Event(),
        lambda _event, _payload: None,
    )

    assert result == "ok"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["keep_alive"] == -1
    assert payload["options"] == {"num_ctx": 262_144}


def test_improvement_baseline_ollama_chat_keeps_model_resident(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post_json(url, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        return {
            "message": {"content": "ok"},
            "done": True,
            "prompt_eval_count": 1,
            "eval_count": 1,
        }

    monkeypatch.setattr(improvement_baseline, "_post_json", fake_post_json)
    manifest = improvement_baseline.load_manifest()
    improvement_baseline._ollama_generate(
        "probe",
        {"model": "fixture-model"},
        manifest["protocol"],
    )

    assert captured["url"] == improvement_baseline.OLLAMA_CHAT_URL
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["keep_alive"] == -1
