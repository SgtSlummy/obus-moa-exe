"""Regression coverage for Codex task-result handoff."""

from __future__ import annotations

import io
import threading
from pathlib import Path

from backend import autonomy


class _FinishedProcess:
    returncode = 0
    stdout = io.StringIO("startup diagnostic\nprovider trace\n")

    def poll(self) -> int:
        return 0


def test_codex_provider_returns_only_final_message_and_cleans_output_file(monkeypatch, tmp_path: Path) -> None:
    """The UI result must not be polluted by the Codex process stream."""

    created_paths: list[Path] = []
    events: list[tuple[str, dict[str, object]]] = []

    def fake_build(_command: str, _prompt: str, *, model: str | None = None,
                   output_path: Path | None = None) -> list[str]:
        assert model is None
        assert output_path is not None
        created_paths.append(output_path)
        output_path.write_text("READY\n", encoding="utf-8")
        return ["codex.exe"]

    monkeypatch.setattr(autonomy, "build_codex_exec_command", fake_build)
    monkeypatch.setattr(autonomy.subprocess, "Popen", lambda *_args, **_kwargs: _FinishedProcess())

    result = autonomy.ProviderRegistry()._run_codex(
        {"workspace": str(tmp_path), "objective": "Report readiness."},
        threading.Event(),
        lambda kind, payload: events.append((kind, payload)),
    )

    assert result == "READY"
    assert events[-1] == ("provider.output", {"provider": "codex", "text": "READY"})
    assert created_paths and not created_paths[0].exists()
