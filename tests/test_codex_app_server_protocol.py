from pathlib import Path

from backend.codex_app_server import CodexAppServer


def test_thread_start_uses_current_workspace_write_protocol(tmp_path: Path):
    bridge = CodexAppServer()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured: list[tuple[str, dict]] = []

    def request(method: str, params: dict, timeout: int = 15) -> dict:
        captured.append((method, params))
        return {"thread": {"id": "thread-safe"}}

    bridge._request = request  # type: ignore[method-assign]
    thread = bridge.start_thread(workspace)

    assert thread["id"] == "thread-safe"
    assert captured == [(
        "thread/start",
        {
            "cwd": str(workspace),
            "sandbox": "workspace-write",
            "approvalPolicy": "on-request",
            "serviceName": "obus",
        },
    )]


def test_thread_resume_uses_current_workspace_write_protocol(tmp_path: Path):
    bridge = CodexAppServer()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    captured: list[tuple[str, dict]] = []

    def request(method: str, params: dict, timeout: int = 15) -> dict:
        captured.append((method, params))
        return {"thread": {"id": "thread-safe", "status": "idle"}}

    bridge._request = request  # type: ignore[method-assign]
    thread = bridge.resume_thread("thread-safe", workspace)

    assert thread["id"] == "thread-safe"
    assert captured == [(
        "thread/resume",
        {
            "threadId": "thread-safe",
            "cwd": str(workspace),
            "sandbox": "workspace-write",
            "approvalPolicy": "on-request",
            "serviceName": "obus",
        },
    )]
