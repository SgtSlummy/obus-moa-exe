from copy import deepcopy

from fastapi.testclient import TestClient

import backend.main as main


MODEL = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M"
PULL_COMMAND = f"ollama pull {MODEL}"


def _state_with_local_preset() -> dict:
    return {"keys": deepcopy(main.DEFAULT_KEYS), "settings": {"selected_model": MODEL}}


def _offline_inventory(*, connected: bool = True) -> dict:
    return {
        "connected": connected,
        "models": [],
        "running_models": [],
        "runtime_contexts": {},
        "model_contexts": {},
    }


def test_desktop_assets_expose_the_unpulled_preset_and_readiness_regions():
    client = TestClient(main.app)
    html = client.get("/").text
    dashboard = client.get("/static/aui/dashboard.js").text
    presets = client.get("/static/aui/ollama-presets.js").text

    assert html.index("/static/aui/ollama-presets.js") < html.index("/static/aui/dashboard.js")
    assert html.count("data-ollama-model-readiness") == 2
    assert "Built-in presets remain selectable before they are pulled" in html
    assert MODEL in presets
    assert "mergeModelOptions" in dashboard
    assert "getReadiness" in dashboard
    assert "find(option=>option.selected)" in dashboard
    assert "Model not pulled" in dashboard
    assert "local?.last_probe_message||readiness.message" in dashboard


def test_qwen_preset_matches_the_built_in_local_key():
    local_key = next(key for key in main.DEFAULT_KEYS if key["id"] == "key-local-ollama")

    assert local_key["model"] == MODEL
    assert local_key["max_context_tokens"] == 262_144


def test_missing_preset_status_explains_how_to_pull_it():
    state = _state_with_local_preset()
    local = next(
        provider
        for provider in main.provider_statuses(state, _offline_inventory())
        if provider["id"] == "key-local-ollama"
    )

    assert local["connected"] is False
    assert local["local_readiness"] == "unavailable"
    assert local["last_probe_reason"] == "model_missing"
    assert "has not been pulled yet" in local["last_probe_message"]
    assert PULL_COMMAND in local["last_probe_message"]


def test_live_probe_and_setup_guide_return_the_exact_pull_command(monkeypatch):
    local_key = next(key for key in _state_with_local_preset()["keys"] if key["id"] == "key-local-ollama")
    monkeypatch.setattr(main, "get_ollama_status", _offline_inventory)

    probe = main.probe_key_live(local_key)
    guide = main.key_setup_guide(local_key)

    assert probe["success"] is False
    assert probe["reason"] == "model_missing"
    assert "has not been pulled yet" in probe["message"]
    assert PULL_COMMAND in probe["message"]
    assert any(PULL_COMMAND in step for step in guide["steps"])
    assert all("<model>" not in step for step in guide["steps"])


def test_auto_aid_missing_model_is_read_only_and_actionable():
    state = _state_with_local_preset()
    before = deepcopy(state)

    preflight = main.local_ollama_auto_aid_preflight(state, _offline_inventory())

    assert preflight["safe"] is False
    assert preflight["auto_apply"] is False
    assert preflight["reason"] == "model_missing"
    assert preflight["model"] == MODEL
    assert PULL_COMMAND in preflight["message"]
    assert state == before
