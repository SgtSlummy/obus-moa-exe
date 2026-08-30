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
from .execution_policy import classify_major_risk
from .secret_safety import redact_text, redact_value
from .parity_capture import task_evidence


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
    provider: str = Field(default="autoagent", pattern="^(autoagent|codex|ollama|openai-compatible)$")
    model: str | None = Field(default=None, max_length=256)
    approval_id: str | None = Field(default=None, pattern=r"^approval-[a-f0-9]{16}$")


class ApprovalCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=65536)
    workspace: str | None = None
    priority: int = Field(default=50, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=10)
    provider: str = Field(default="autoagent", pattern="^(autoagent|codex|ollama|openai-compatible)$")
    model: str | None = Field(default=None, max_length=256)


class ApprovalDecision(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _existing_workspace(value: str | None) -> Path:
    """Resolve a task root without granting the API directory-creation authority."""

    try:
        workspace = (Path(value).expanduser() if value else Path.cwd()).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail="Task workspace must already exist") from exc
    if not workspace.is_dir():
        raise HTTPException(status_code=400, detail="Task workspace must be a directory")
    return workspace


def _public_task(task: dict) -> dict:
    """Keep durable task metadata useful in the UI without exposing secrets."""

    public = dict(task)
    for field, limit in (("objective", 4000), ("workspace", 1000), ("result", 16000), ("error", 4000)):
        if public.get(field) is not None:
            public[field] = redact_text(public[field], limit)
    return public


def _public_event(event: dict) -> dict:
    public = dict(event)
    public["payload"] = redact_value(event.get("payload") or {})
    return public


def _public_approval(approval: dict) -> dict:
    """Expose a reviewable local decision without returning an unredacted objective."""

    public = dict(approval)
    public["objective_preview"] = redact_text(public.get("objective_preview"), 1200)
    public["workspace"] = redact_text(public.get("workspace"), 1000)
    public["decision_note"] = redact_text(public.get("decision_note"), 1000)
    public["objective_fingerprint"] = str(public.pop("objective_sha256", ""))[:16]
    return public


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
        "mode": "guarded-autonomous",
        "approval_required": "major-destructive-or-hardware-risk",
        "approval_flow": "local-request-review-approve-once",
        "remote_authority": "workspace-guarded",
        "capabilities": [
            "codex.auto-review", "shell.local-terminal", "filesystem.workspace-write", "process.workspace",
            "git.workspace", "packages.workspace", "self.repair",
            "learning.immediate", "goals.proactive", "local-model.workspace-tool-loop",
        ],
        "blocked_without_local_approval": [
            "bulk-or-irrecoverable-deletion", "boot-firmware-or-disk-layout",
            "hardware-safety-controls", "security-or-recovery-disablement",
        ],
        "source": source,
    }


def _require_local_approval_source(source: str) -> None:
    if source != "local":
        raise HTTPException(status_code=403, detail="Major-risk approvals can only be reviewed on the local desktop")


def _ensure_major_risk_approval(payload: ApprovalCreate | TaskCreate, workspace: Path, risks: list[str]) -> dict:
    return runtime.store.ensure_approval(
        payload.objective.strip(), workspace, risks, payload.provider, payload.model,
        payload.priority, payload.max_attempts,
    )


@router.get("/approvals")
def list_harness_approvals(request: Request, authorization: Annotated[str | None, Header()] = None,
                           limit: int = Query(default=100, ge=1, le=500)):
    _require_local_approval_source(_authorize(request, authorization))
    return {"approvals": [_public_approval(item) for item in runtime.store.list_approvals(limit)]}


@router.post("/approvals", status_code=201)
def create_harness_approval(payload: ApprovalCreate, request: Request,
                            authorization: Annotated[str | None, Header()] = None):
    _require_local_approval_source(_authorize(request, authorization))
    risks = classify_major_risk(payload.objective)
    if not risks:
        raise HTTPException(status_code=400, detail="Only major destructive or hardware-risk tasks need an approval request")
    workspace = _existing_workspace(payload.workspace)
    return _public_approval(_ensure_major_risk_approval(payload, workspace, risks))


@router.post("/approvals/{approval_id}/approve")
def approve_harness_approval(approval_id: str, payload: ApprovalDecision, request: Request,
                             authorization: Annotated[str | None, Header()] = None):
    _require_local_approval_source(_authorize(request, authorization))
    try:
        return _public_approval(runtime.store.decide_approval(approval_id, "approved", payload.note))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/reject")
def reject_harness_approval(approval_id: str, payload: ApprovalDecision, request: Request,
                            authorization: Annotated[str | None, Header()] = None):
    _require_local_approval_source(_authorize(request, authorization))
    try:
        return _public_approval(runtime.store.decide_approval(approval_id, "rejected", payload.note))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="approval not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/tasks", status_code=202)
def create_harness_task(payload: TaskCreate, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    source = _authorize(request, authorization)
    major_risks = classify_major_risk(payload.objective)
    if major_risks and source != "local":
        raise HTTPException(
            status_code=403,
            detail={"message": "Major-risk tasks require approval from the local desktop", "risks": major_risks},
        )
    workspace = _existing_workspace(payload.workspace)
    approval = None
    if major_risks:
        _require_local_approval_source(source)
        if not payload.approval_id:
            approval = _ensure_major_risk_approval(payload, workspace, major_risks)
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "A local approval request was created. Review and approve it before starting this one-time task.",
                    "risks": major_risks, "approval_id": approval["id"],
                },
            )
        try:
            approval = runtime.store.consume_approval(
                payload.approval_id, payload.objective.strip(), workspace, major_risks, payload.provider,
                payload.model, payload.priority, payload.max_attempts,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="approval not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    try:
        task = runtime.submit(payload.objective.strip(), workspace, source, payload.priority, payload.max_attempts,
                              payload.provider, payload.model)
    except Exception:
        if approval is not None:
            runtime.store.release_approval(approval["id"])
        raise
    if approval is not None:
        runtime.store.attach_approval_task(approval["id"], task["id"])
        runtime.store.add_event(task["id"], "approval.consumed", {
            "approval_id": approval["id"], "risks": major_risks, "decision": "explicit-local-once",
        })
    return _public_task(task)


@router.get("/tasks")
def list_harness_tasks(request: Request, authorization: Annotated[str | None, Header()] = None,
                       limit: int = Query(default=100, ge=1, le=500)):
    _authorize(request, authorization)
    return {"tasks": [_public_task(task) for task in runtime.store.list_tasks(limit)]}


@router.get("/tasks/{task_id}")
def get_harness_task(task_id: str, request: Request,
                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return _public_task(runtime.store.get_task(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc


@router.delete("/tasks/{task_id}", status_code=202)
def cancel_harness_task(task_id: str, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return _public_task(runtime.cancel(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc


@router.get("/tasks/{task_id}/parity-evidence")
def get_harness_task_parity_evidence(task_id: str, request: Request,
                                     authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        return task_evidence(runtime.store.get_task(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc


@router.post("/tasks/{task_id}/resume", status_code=202)
def resume_harness_task(task_id: str, request: Request,
                        authorization: Annotated[str | None, Header()] = None):
    _require_local_approval_source(_authorize(request, authorization))
    try:
        task = runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc
    if task["state"] != "interrupted":
        raise HTTPException(status_code=409, detail="Only interrupted tasks can be resumed")
    risks = classify_major_risk(task["objective"])
    if risks:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Major-risk work is never resumed after a restart. Submit it again and obtain a fresh local approval.",
                "risks": risks,
            },
        )
    try:
        return _public_task(runtime.resume(task_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/events")
def get_harness_events(task_id: str, request: Request,
                       authorization: Annotated[str | None, Header()] = None,
                       after: int = Query(default=0, ge=0)):
    _authorize(request, authorization)
    try:
        runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Harness task not found") from exc
    return {"events": [_public_event(event) for event in runtime.store.events(task_id, after)]}


@router.get("/tasks/{task_id}/changes")
def get_harness_task_changes(task_id: str, request: Request,
                             authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    try:
        return runtime.recovery.task_changes(task_id)
    except KeyError:
        return {
            "task_id": task_id, "checkpoint": None, "changes": [], "counts": {}, "truncated": False,
            "read_only": True, "reason": "This task has not created a workspace checkpoint yet.",
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/changes/{relative_path:path}")
def get_harness_task_change_diff(task_id: str, relative_path: str, request: Request,
                                 authorization: Annotated[str | None, Header()] = None):
    _authorize(request, authorization)
    try:
        runtime.store.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc
    try:
        return runtime.recovery.task_change_diff(task_id, relative_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="task checkpoint not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
            events = [_public_event(event) for event in runtime.store.events(task_id, sequence)]
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
    lessons = []
    for lesson in runtime.store.lessons(limit):
        public = dict(lesson)
        public["objective"] = redact_text(public.get("objective"), 4000)
        public["content"] = redact_text(public.get("content"), 16000)
        lessons.append(public)
    return {"promotion": "immediate", "lessons": lessons}
