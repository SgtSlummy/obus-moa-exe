from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import backend.main as backend
from backend.terminal_api import terminal_registry


class _Session:
    def __init__(self, cwd: str):
        self.cwd = Path(cwd)

    def snapshot(self):
        return {"id": "term-scoped", "shell": "pwsh", "cwd": str(self.cwd), "alive": True}


def test_terminal_requires_a_selected_workspace(monkeypatch):
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: None)

    response = TestClient(backend.app).post("/api/terminal/sessions", json={"shell": "pwsh"})

    assert response.status_code == 409
    assert "Choose a valid local workspace" in response.json()["detail"]


def test_terminal_cwd_is_scoped_to_the_selected_workspace(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    child = workspace / "tools"
    child.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))
    create = AsyncMock(return_value=_Session(str(child)))
    monkeypatch.setattr(terminal_registry, "create", create)
    client = TestClient(backend.app)

    rejected = client.post("/api/terminal/sessions", json={"shell": "pwsh", "cwd": str(outside)})
    accepted = client.post("/api/terminal/sessions", json={"shell": "pwsh", "cwd": str(child)})

    assert rejected.status_code == 422
    assert "stay inside the selected workspace" in rejected.json()["detail"]
    assert accepted.status_code == 201
    assert create.await_args.args[1] == str(child.resolve())


def test_terminal_input_refuses_a_session_from_another_workspace(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    session = _Session(str(outside))
    monkeypatch.setattr(backend.app.state, "terminal_workspace_root", lambda: str(workspace))
    monkeypatch.setattr(terminal_registry, "get", lambda _session_id: session)

    response = TestClient(backend.app).post(
        "/api/terminal/sessions/term-other/input",
        json={"data": "Get-Location\r"},
    )

    assert response.status_code == 409
    assert "different workspace" in response.json()["detail"]
