from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.autonomy import ProviderRegistry


def test_pre_cancelled_autoagent_task_never_starts_a_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cancellation = threading.Event()
    cancellation.set()
    started: list[tuple[object, ...]] = []

    def forbidden_popen(*args: object, **_kwargs: object) -> object:
        started.append(args)
        raise AssertionError("a pre-cancelled AutoAgent task must not launch a process")

    monkeypatch.setattr("backend.autonomy.subprocess.Popen", forbidden_popen)

    with pytest.raises(InterruptedError, match="task cancelled"):
        ProviderRegistry._run_autoagent(
            None,
            {"objective": "Do not start", "workspace": str(tmp_path)},
            cancellation,
            lambda _kind, _payload: None,
        )

    assert started == []
