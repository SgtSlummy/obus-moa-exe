"""Local desktop API and WebSocket transport for ConPTY sessions."""
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from .terminal_runtime import TerminalUnavailable, terminal_registry
from .workspace_context import workspace_status


router = APIRouter(prefix="/api/terminal", tags=["desktop-terminal"])


def _is_local(host: str | None) -> bool:
    return (host or "").split("%", 1)[0].lower() in {"127.0.0.1", "::1", "localhost", "testclient"}


class TerminalStart(BaseModel):
    shell: str = Field(default="pwsh", pattern=r"^(pwsh|powershell|cmd)$")
    cwd: str | None = Field(default=None, max_length=1000)
    rows: int = Field(default=32, ge=8, le=200)
    cols: int = Field(default=120, ge=20, le=400)


class TerminalInput(BaseModel):
    data: str = Field(min_length=1, max_length=65_536)


class TerminalResize(BaseModel):
    rows: int = Field(ge=8, le=200)
    cols: int = Field(ge=20, le=400)


def _local_request(request: Request) -> None:
    if not _is_local(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="Terminal access is local-only")


def _selected_workspace_root(app) -> Path:
    """Return the explicitly selected local workspace for a terminal session.

    The shell is an interactive, human-operated escape hatch, but it must not
    silently turn the local dashboard into an arbitrary-directory launcher.
    ``backend.main`` supplies the state-backed provider once its settings
    helpers are initialized; leaving it unset fails closed for standalone API
    tests or accidental router reuse.
    """

    provider = getattr(app.state, "terminal_workspace_root", None)
    configured_root = provider() if callable(provider) else None
    workspace = workspace_status(configured_root)
    if not workspace.get("valid"):
        raise HTTPException(
            status_code=409,
            detail="Choose a valid local workspace before opening a terminal.",
        )
    return Path(str(workspace["root"])).resolve(strict=True)


def _terminal_cwd(root: Path, requested_cwd: str | None) -> Path:
    if not requested_cwd or not requested_cwd.strip():
        return root
    try:
        cwd = Path(requested_cwd).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail="Terminal directory not found.") from exc
    if not cwd.is_dir():
        raise HTTPException(status_code=422, detail="terminal cwd must be an existing directory")
    try:
        cwd.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="terminal cwd must stay inside the selected workspace",
        ) from exc
    return cwd


def _session_in_workspace(session, root: Path) -> bool:
    try:
        session.cwd.resolve(strict=True).relative_to(root)
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _workspace_session(session_id: str, app):
    root = _selected_workspace_root(app)
    try:
        session = terminal_registry.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not _session_in_workspace(session, root):
        raise HTTPException(status_code=409, detail="Terminal session belongs to a different workspace.")
    return session


@router.get("/sessions")
async def list_terminal_sessions(request: Request):
    _local_request(request)
    root = _selected_workspace_root(request.app)
    sessions = [
        session for session in terminal_registry.list()
        if _session_in_workspace(terminal_registry.get(str(session["id"])), root)
    ]
    return {"sessions": sessions}


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def start_terminal_session(payload: TerminalStart, request: Request):
    _local_request(request)
    root = _selected_workspace_root(request.app)
    cwd = _terminal_cwd(root, payload.cwd)
    try:
        session = await terminal_registry.create(payload.shell, str(cwd), payload.rows, payload.cols)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=f"Terminal directory not found: {exc.filename}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (RuntimeError, TerminalUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return session.snapshot()


@router.post("/sessions/{session_id}/input", status_code=status.HTTP_202_ACCEPTED)
async def send_terminal_input(session_id: str, payload: TerminalInput, request: Request):
    _local_request(request)
    session = _workspace_session(session_id, request.app)
    await session.write(payload.data)
    return {"accepted": True, "alive": session.alive}


@router.patch("/sessions/{session_id}/size")
async def resize_terminal(session_id: str, payload: TerminalResize, request: Request):
    _local_request(request)
    session = _workspace_session(session_id, request.app)
    await session.resize(payload.rows, payload.cols)
    return session.snapshot()


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_terminal_session(session_id: str, request: Request):
    _local_request(request)
    try:
        await terminal_registry.close(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.websocket("/sessions/{session_id}/stream")
async def terminal_stream(websocket: WebSocket, session_id: str):
    if not _is_local(websocket.client.host if websocket.client else None):
        await websocket.close(code=4403, reason="terminal access is local-only")
        return
    try:
        session = _workspace_session(session_id, websocket.app)
    except HTTPException as exc:
        code = 4404 if exc.status_code == 404 else 4409
        await websocket.close(code=code, reason=str(exc.detail))
        return
    except KeyError:
        await websocket.close(code=4404, reason="terminal session not found")
        return
    await websocket.accept()
    queue = session.subscribe()

    async def sender() -> None:
        while True:
            chunk = await queue.get()
            if chunk is None:
                await websocket.send_json({"type": "status", "alive": False})
                return
            await websocket.send_json({"type": "output", "data": chunk})

    async def receiver() -> None:
        while True:
            message = await websocket.receive_json()
            kind = message.get("type")
            if kind == "input":
                data = str(message.get("data") or "")[:65_536]
                if data:
                    await session.write(data)
            elif kind == "resize":
                rows = max(8, min(int(message.get("rows") or session.rows), 200))
                cols = max(20, min(int(message.get("cols") or session.cols), 400))
                await session.resize(rows, cols)

    send_task = asyncio.create_task(sender())
    receive_task = asyncio.create_task(receiver())
    try:
        done, pending = await asyncio.wait(
            {send_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        for task in done:
            with contextlib.suppress(WebSocketDisconnect):
                task.result()
    except WebSocketDisconnect:
        pass
    finally:
        session.unsubscribe(queue)
