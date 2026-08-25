"""Checkpoint and recovery API for autonomous task repair."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.harness_api import _authorize, runtime

router = APIRouter(prefix="/api/harness", tags=["harness-recovery"])


class CheckpointCreate(BaseModel):
    task_id: str = Field(min_length=1, max_length=128)
    workspace: str = Field(min_length=1, max_length=32768)


@router.get("/checkpoints")
def list_checkpoints(request: Request, task_id: str | None = None, limit: int = 100,
                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    return {"checkpoints": runtime.recovery.list(task_id, limit)}


@router.get("/checkpoints/{checkpoint_id}")
def get_checkpoint(checkpoint_id: str, request: Request,
                   authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return runtime.recovery.get(checkpoint_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="checkpoint not found") from exc


@router.post("/checkpoints", status_code=201)
def create_checkpoint(payload: CheckpointCreate, request: Request,
                      authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    workspace = Path(payload.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise HTTPException(status_code=422, detail="workspace must be an existing directory")
    return runtime.recovery.create(payload.task_id, workspace)


@router.post("/checkpoints/{checkpoint_id}/rollback")
def rollback_checkpoint(checkpoint_id: str, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return runtime.recovery.rollback(checkpoint_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="checkpoint not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
