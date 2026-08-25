"""Lazy local-first voice state and transcript routing for the autonomous harness."""

from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path
from typing import Any, Callable


class VoiceController:
    def __init__(self, submit: Callable[..., dict[str, Any]]):
        self.submit = submit
        self._lock = threading.Lock()
        self._muted = os.environ.get("OBUS_VOICE_MUTED", "0").lower() in {"1", "true", "yes", "on"}
        self._listening = False
        self._wake_word = os.environ.get("OBUS_VOICE_WAKE_WORD", "jarvis").strip() or "jarvis"

    def status(self) -> dict[str, Any]:
        model_path = Path(os.environ["OBUS_LOCAL_STT_MODEL_PATH"]).expanduser() if os.environ.get("OBUS_LOCAL_STT_MODEL_PATH") else None
        local_dependencies = bool(importlib.util.find_spec("faster_whisper") and importlib.util.find_spec("sounddevice"))
        local_ready = bool(local_dependencies and model_path and model_path.exists())
        cloud_configured = bool(os.environ.get("OBUS_VOICE_CLOUD_URL") and os.environ.get("OBUS_VOICE_CLOUD_TOKEN"))
        with self._lock:
            return {
                "mode": "local-first-hybrid", "wake_word": self._wake_word,
                "muted": self._muted, "listening": self._listening,
                "local_ready": local_ready, "local_dependencies": local_dependencies,
                "model_path_configured": bool(model_path), "cloud_fallback_configured": cloud_configured,
                "ready": bool(not self._muted and (local_ready or cloud_configured)),
            }

    def set_muted(self, muted: bool) -> dict[str, Any]:
        with self._lock:
            self._muted = bool(muted)
            if self._muted:
                self._listening = False
        return self.status()

    def set_listening(self, listening: bool) -> dict[str, Any]:
        with self._lock:
            if self._muted and listening:
                raise RuntimeError("voice is muted")
            self._listening = bool(listening)
        return self.status()

    def submit_transcript(self, transcript: str, workspace: Path | str | None = None, provider: str = "codex",
                          model: str | None = None, source: str = "voice") -> dict[str, Any]:
        text = transcript.strip()
        if not text:
            raise ValueError("transcript is empty")
        with self._lock:
            if self._muted:
                raise RuntimeError("voice is muted")
            self._listening = False
        workspace_path = Path(workspace) if workspace is not None else Path.cwd()
        return self.submit(text, workspace_path, source=source, priority=70, provider=provider, model=model)
