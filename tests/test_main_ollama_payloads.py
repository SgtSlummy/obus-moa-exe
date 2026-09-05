import json
from types import SimpleNamespace

import backend.main as main


MODEL = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M"
CONTEXT_TOKENS = 262_144


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, *_args):
        return self._payload


class _CaptureOpener:
    def __init__(self, response_payload: dict):
        self.response_payload = response_payload
        self.payloads = []

    def open(self, request, timeout):
        self.payloads.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse(self.response_payload)


def test_direct_ollama_payloads_preserve_residency_and_context(monkeypatch):
    settings = {
        "per_agent_context_window": CONTEXT_TOKENS,
        "auto_parallelize": True,
        "autonomy_level": "high",
    }
    status = {
        "connected": True,
        "models": [MODEL],
        "model_contexts": {MODEL: CONTEXT_TOKENS},
    }
    monkeypatch.setattr(main, "OLLAMA_KEEP_ALIVE", -1)
    monkeypatch.setattr(main, "get_ollama_status", lambda: status)
    monkeypatch.setattr(main, "get_settings", lambda *_args, **_kwargs: settings)
    monkeypatch.setattr(
        main,
        "resolve_context_window",
        lambda model, ollama_status, runtime_settings, **_kwargs: CONTEXT_TOKENS,
    )

    thor = _CaptureOpener({"response": "OK", "prompt_eval_count": 1, "eval_count": 1})
    monkeypatch.setattr(main, "_NO_REDIRECT_OPENER", thor)
    main._thor_local_generate("ping", MODEL)

    orchestrator = _CaptureOpener({"response": "{}"})
    monkeypatch.setattr(main, "_NO_REDIRECT_OPENER", orchestrator)
    monkeypatch.setattr(main, "select_cards_for_prompt", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(main, "autonomy_directive", lambda *_args, **_kwargs: "")
    main.primary_orchestrator_complete(
        objective="plan",
        state={
            "keys": [
                {
                    "provider": "ollama",
                    "state": "ready",
                    "model": MODEL,
                    "max_context_tokens": CONTEXT_TOKENS,
                }
            ],
            "cards": [],
        },
        max_agents=1,
    )

    generated = _CaptureOpener({"response": "OK", "prompt_eval_count": 2, "eval_count": 1})
    monkeypatch.setattr(main, "load_state", lambda: {})
    monkeypatch.setattr(
        main,
        "guard_epistemic_request",
        lambda _prompt: SimpleNamespace(blocked=False, response=None),
    )
    monkeypatch.setattr(main, "epistemic_policy", lambda: "")
    monkeypatch.setattr(
        main,
        "open_loopback_request",
        lambda request, timeout: generated.open(request, timeout),
    )
    main.generate_with_ollama(
        "ping",
        MODEL,
        {
            "agents": {"dynamic_assignments": []},
            "selected_deck": {"name": "Rider-Waite"},
        },
        images=[{"data_base64": "aW1hZ2U="}],
    )

    payloads = [thor.payloads[-1], orchestrator.payloads[-1], generated.payloads[-1]]
    assert all(payload["model"] == MODEL for payload in payloads)
    assert all(payload["stream"] is False for payload in payloads)
    assert all(payload["keep_alive"] == -1 for payload in payloads)
    assert all(payload["options"]["num_ctx"] == CONTEXT_TOKENS for payload in payloads)
    assert "system" in thor.payloads[-1]
    assert orchestrator.payloads[-1]["format"] == "json"
    assert generated.payloads[-1]["images"] == ["aW1hZ2U="]
