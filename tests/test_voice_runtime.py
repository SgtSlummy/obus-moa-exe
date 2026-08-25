from __future__ import annotations

from pathlib import Path

from backend.voice_runtime import VoiceController


def test_voice_status_is_local_first_and_lazy(monkeypatch):
    monkeypatch.delenv("OBUS_VOICE_CLOUD_URL", raising=False)
    monkeypatch.delenv("OBUS_VOICE_CLOUD_TOKEN", raising=False)
    monkeypatch.setattr("backend.voice_runtime.importlib.util.find_spec", lambda _name: None)

    controller = VoiceController(lambda **_kwargs: "unused")
    state = controller.status()

    assert state["mode"] == "local-first-hybrid"
    assert state["muted"] is False
    assert state["listening"] is False
    assert state["local_ready"] is False
    assert state["cloud_fallback_configured"] is False


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
    monkeypatch.setattr("backend.voice_runtime.importlib.util.find_spec", lambda _name: None)

    state = VoiceController(lambda **_kwargs: "unused").status()

    assert state["cloud_fallback_configured"] is True
    assert state["ready"] is True
