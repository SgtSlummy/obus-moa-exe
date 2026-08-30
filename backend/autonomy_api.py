"""Provider and proactive-objective API extensions for the autonomous harness."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.agent_harness import TERMINAL_STATES
from backend.autonomy import ObjectiveScheduler
from backend.execution_policy import classify_major_risk
from backend.harness_api import _authorize, runtime

router = APIRouter(prefix="/api/harness", tags=["harness-autonomy"])


def _task_is_active(task_id: str) -> bool:
    try:
        return str(runtime.store.get_task(task_id).get("state") or "") not in TERMINAL_STATES
    except KeyError:
        return False


objective_scheduler = ObjectiveScheduler(
    runtime.store.path,
    runtime.submit,
    poll_seconds=float(os.environ.get("OBUS_OBJECTIVE_POLL_SECONDS", "1")),
    task_active=_task_is_active,
)
if os.environ.get("OBUS_PROACTIVE_OBJECTIVES", "1").strip().lower() not in {"0", "false", "no", "off"}:
    objective_scheduler.start()


class ObjectiveCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    objective: str = Field(min_length=1, max_length=65536)
    workspace: str | None = None
    interval_seconds: int = Field(ge=1, le=31_536_000)
    provider: str = Field(default="autoagent", pattern="^(autoagent|codex|ollama|openai-compatible)$")
    priority: int = Field(default=50, ge=0, le=100)
    enabled: bool = True


class ObjectiveEnabled(BaseModel):
    enabled: bool


@router.get("/providers")
def list_harness_providers(request: Request, authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    return runtime.providers.capabilities()


@router.get("/objectives")
def list_objectives(request: Request, authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    return {"objectives": objective_scheduler.list()}


@router.post("/objectives", status_code=201)
def create_objective(payload: ObjectiveCreate, request: Request,
                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    risks = classify_major_risk(payload.objective)
    if risks:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Major-risk objectives cannot run on a schedule. Start a one-time task from the local desktop instead.",
                "risks": risks,
            },
        )
    try:
        workspace = (Path(payload.workspace).expanduser() if payload.workspace else Path.cwd()).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail="Scheduled workspace must already exist") from exc
    if not workspace.is_dir():
        raise HTTPException(status_code=400, detail="Scheduled workspace must be a directory")
    return objective_scheduler.create(payload.name.strip(), payload.objective.strip(), workspace,
                                      payload.interval_seconds, payload.provider, payload.priority, payload.enabled)


@router.patch("/objectives/{objective_id}")
def set_objective_enabled(objective_id: str, payload: ObjectiveEnabled, request: Request,
                          authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return objective_scheduler.set_enabled(objective_id, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="objective not found") from exc


@router.delete("/objectives/{objective_id}", status_code=204)
def delete_objective(objective_id: str, request: Request,
                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        objective_scheduler.delete(objective_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="objective not found") from exc
    return None


@router.post("/objectives/run-due")
def run_due_objectives(request: Request, authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    return {"task_ids": objective_scheduler.run_due()}
