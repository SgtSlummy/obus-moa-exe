"""HTTP contracts for the durable OBus autonomous harness."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent_harness import AgentHarnessRuntime, TERMINAL_STATES


def _database_path() -> Path:
    root = Path(os.environ.get("OBUS_STATE_DIR") or os.environ.get("LOCALAPPDATA") or Path.home() / ".obus")
    return root / "Obus" / "harness.sqlite3"


runtime = AgentHarnessRuntime(
    _database_path(),
    max_workers=max(1, min(int(os.environ.get("OBUS_HARNESS_WORKERS", "2")), 8)),
)
router = APIRouter(prefix="/api/harness", tags=["harness"])


class TaskCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=65536)
    workspace: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=10)
    provider: str = Field(default="codex", pattern="^(codex|ollama|openai-compatible)$")
    model: str | None = Field(default=None, max_length=256)


def _authorize(request: Request, authorization: Annotated[str | None, Header()] = None) -> str:
    host = (request.client.host if request.client else "").split("%", 1)[0].lower()
    if host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return "local"
    token = os.environ.get("OBUS_THOR_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(status_code=503, detail="Remote harness authentication is not configured")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid harness authorization")
    return "thor"


@router.get("/health")
def harness_health(source: Annotated[str, Depends(_authorize)]):
    return runtime.health() | {"source": source}


@router.get("/capabilities")
def harness_capabilities(source: Annotated[str, Depends(_authorize)]):
    return {
        "mode": "unrestricted",
        "approval_required": False,
        "remote_authority": "full",
        "capabilities": [
            "codex.unrestricted", "shell.powershell", "filesystem.full", "process.full", "git.full",
            "windows.services", "windows.registry", "packages.manage", "network.manage", "self.repair",
            "learning.immediate", "goals.proactive",
        ],
        "source": source,
    }


@router.post("/tasks", status_code=202)
def create_harness_task(payload: TaskCreate, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    source = _authorize(request, authorization)
    workspace = Path(payload.workspace).expanduser() if payload.workspace else Path.cwd()
    return runtime.submit(payload.objective.strip(), workspace, source, payload.priority, payload.max_attempts,
                          payload.provider, payload.model)


@router.get("/tasks")
def list_harness_tasks(request: Request, authorization: Annotated[str | None, Header()] = None,
                       limit: int = Query(default=100, ge=1, le=500)):
    _authorize(request, authorization)
    return {"tasks": runtime.store.list_tasks(limit)}


@router.get("/tasks/{task_id}")
def get_harness_task(task_id: str, request: Request,
                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc


@router.delete("/tasks/{task_id}", status_code=202)
def cancel_harness_task(task_id: str, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return runtime.cancel(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc


@router.get("/tasks/{task_id}/events")
def get_harness_events(task_id: str, request: Request,
                       authorization: Annotated[str | None, Header()] = None,
                       after: int = Query(default=0, ge=0)):
    _authorize(request, authorization)
    try:
        runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc
    return {"events": runtime.store.events(task_id, after)}


@router.get("/tasks/{task_id}/events/stream")
def stream_harness_events(task_id: str, request: Request,
                          authorization: Annotated[str | None, Header()] = None,
                          after: int = Query(default=0, ge=0)):
    _authorize(request, authorization)
    try:
        runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc

    async def event_stream():
        sequence = after
        idle_ticks = 0
        while True:
            events = runtime.store.events(task_id, sequence)
            for event in events:
                sequence = int(event["sequence"])
                yield f"id: {sequence}\nevent: {event['event_type']}\ndata: {json.dumps(event)}\n\n"
                idle_ticks = 0
            task = runtime.store.get_task(task_id)
            if task["state"] in TERMINAL_STATES and not events:
                break
            idle_ticks += 1
            if idle_ticks % 15 == 0:
                yield ": keepalive\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/lessons")
def list_harness_lessons(request: Request, authorization: Annotated[str | None, Header()] = None,
                         limit: int = Query(default=100, ge=1, le=500)):
    _authorize(request, authorization)
    return {"promotion": "immediate", "lessons": runtime.store.lessons(limit)}
