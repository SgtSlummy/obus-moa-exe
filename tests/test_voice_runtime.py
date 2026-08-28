from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import backend.main as backend
from backend.voice_api import get_voice_status
from backend.voice_runtime import VoiceController


def test_voice_status_is_local_first_and_lazy(monkeypatch):
    monkeypatch.delenv("OBUS_VOICE_CLOUD_URL", raising=False)
    monkeypatch.delenv("OBUS_VOICE_CLOUD_TOKEN", raising=False)
    monkeypatch.setattr("backend.voice_runtime.faster_whisper_available", lambda: False)

    controller = VoiceController(lambda **_kwargs: "unused")
    state = controller.status()

    assert state["mode"] == "local-first-hybrid"
    assert state["muted"] is False
    assert state["listening"] is False
    assert state["local_ready"] is False
    assert state["cloud_fallback_configured"] is False


def test_browser_captured_voice_needs_only_faster_whisper_and_a_local_model(monkeypatch, tmp_path):
    model_path = tmp_path / "faster-whisper-model"
    model_path.mkdir()
    monkeypatch.setenv("OBUS_LOCAL_STT_MODEL_PATH", str(model_path))
    monkeypatch.setattr("backend.voice_runtime.faster_whisper_available", lambda: True)
    monkeypatch.setattr("backend.main.faster_whisper_available", lambda: True)

    controller_state = VoiceController(lambda **_kwargs: "unused").status()
    dashboard_state = backend.local_voice_status()

    assert controller_state["local_dependencies"] is True
    assert controller_state["local_ready"] is True
    assert controller_state["ready"] is True
    assert dashboard_state["dependencies_available"] is True
    assert dashboard_state["ready"] is True


def test_auto_aid_selects_one_complete_existing_local_voice_model_without_download(monkeypatch, tmp_path):
    model = tmp_path / "models" / "faster-whisper-base.en"
    model.mkdir(parents=True)
    (model / "model.bin").write_bytes(b"model")
    (model / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.delenv("OBUS_LOCAL_STT_MODEL_PATH", raising=False)
    monkeypatch.setattr(backend, "faster_whisper_available", lambda: True)

    state = backend.normalize_state({})
    result = backend.auto_aid_local_voice_model(state)

    assert result["success"] is True
    assert result["auto_apply"] is True
    assert result["model"] == "faster-whisper-base.en"
    assert state["voice_setup"]["local_model_path"] == str(model.resolve())
    assert backend.local_voice_status(state)["ready"] is True
    assert "download" in result["message"].lower()


def test_auto_aid_refuses_to_choose_between_multiple_local_voice_models(monkeypatch, tmp_path):
    for name in ("faster-whisper-base.en", "faster-whisper-small.en"):
        model = tmp_path / "models" / name
        model.mkdir(parents=True)
        (model / "model.bin").write_bytes(b"model")
        (model / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backend, "DATA_DIR", tmp_path)
    monkeypatch.delenv("OBUS_LOCAL_STT_MODEL_PATH", raising=False)
    monkeypatch.setattr(backend, "faster_whisper_available", lambda: True)

    state = backend.normalize_state({})
    result = backend.auto_aid_local_voice_model(state)

    assert result["success"] is False
    assert result["auto_apply"] is False
    assert len(result["candidates"]) == 2
    assert state["voice_setup"]["local_model_path"] is None


def test_harness_voice_status_reuses_the_canonical_local_model_resolver():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                local_voice_status=lambda: {
                    "ready": True,
                    "model_path_configured": True,
                    "model_source": "bundled-offline",
                    "reason": "Ready for local speech transcription",
                }
            )
        )
    )

    status = get_voice_status(request)

    assert status["local_ready"] is True
    assert status["model_path_configured"] is True
    assert status["model_source"] == "bundled-offline"
    assert status["ready"] is True


def test_muted_voice_cannot_listen_or_submit():
    controller = VoiceController(lambda **_kwargs: "unused")
    state = controller.set_muted(True)

    assert state["muted"] is True
    assert state["listening"] is False
    for action in (lambda: controller.set_listening(True), lambda: controller.submit_transcript("do the thing")):
        try:
            action()
        except RuntimeError as exc:
            assert "muted" in str(exc).lower()
        else:
            raise AssertionError("muted voice unexpectedly accepted work")


def test_transcript_routes_to_harness_with_voice_metadata():
    captured: dict[str, object] = {}

    def submit(prompt, workspace, **kwargs):
        captured.update({"prompt": prompt, "workspace": str(workspace), **kwargs})
        return {"id": "objective-123"}

    objective_id = VoiceController(submit).submit_transcript(
        "inspect the workspace", workspace="C:/work", provider="codex", model="gpt-5"
    )

    assert objective_id == {"id": "objective-123"}
    assert captured == {
        "prompt": "inspect the workspace",
        "workspace": str(Path("C:/work")),
        "provider": "codex",
        "model": "gpt-5",
        "priority": 70,
        "source": "voice",
    }


def test_cloud_fallback_reports_configured(monkeypatch):
    monkeypatch.setenv("OBUS_VOICE_CLOUD_URL", "https://voice.example.invalid/transcribe")
    monkeypatch.setenv("OBUS_VOICE_CLOUD_TOKEN", "secret")
    monkeypatch.setattr("backend.voice_runtime.faster_whisper_available", lambda: False)

    state = VoiceController(lambda **_kwargs: "unused").status()

    assert state["cloud_fallback_configured"] is True
    assert state["ready"] is True


def test_voice_composer_is_explicit_local_and_requires_manual_review():
    html = (Path(__file__).resolve().parents[1] / "backend" / "static" / "index.html").read_text(encoding="utf-8")

    for marker in (
        'id="route-voice-button"',
        'id="route-voice-setup"',
        'data-route-voice',
        'data-route-voice-setup',
        '/api/voice/auto-aid',
        'Auto-set up voice',
        'Requesting microphone permission',
        'Transcribing locally',
        'Transcript added — review it, then choose Begin.',
        'echoCancellation:true',
        'noiseSuppression:true',
        'autoGainControl:true',
        'never starts a task from speech alone',
        'never downloads a model',
    ):
        assert marker in html
