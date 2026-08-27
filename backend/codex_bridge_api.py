"""Local API surface for OBus's optional Codex App Server bridge."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from .codex_app_server import CodexAppServer, CodexAppServerError
from .codex_bridge_store import CodexBridgeThreadStore
from .execution_policy import classify_major_risk
from .workspace_context import workspace_status


bridge = CodexAppServer()
thread_store = CodexBridgeThreadStore()


@asynccontextmanager
async def _bridge_lifespan(_app):
    yield
    bridge.close()


router = APIRouter(prefix="/api/codex-bridge", tags=["codex-app-server"], lifespan=_bridge_lifespan)


class CodexThreadStart(BaseModel):
    model: Optional[str] = Field(default=None, max_length=160)


class CodexTurnStart(BaseModel):
    prompt: str = Field(min_length=1, max_length=120_000)
    model: Optional[str] = Field(default=None, max_length=160)


class CodexParallelTurnStart(CodexTurnStart):
    workers: int = Field(default=3, ge=2, le=4)


class CodexParallelSynthesis(BaseModel):
    worker_thread_ids: list[str] = Field(min_length=2, max_length=4)
    model: Optional[str] = Field(default=None, max_length=160)


class CodexReviewedTaskStart(BaseModel):
    model: Optional[str] = Field(default=None, max_length=160)


class CodexApprovalDecision(BaseModel):
    decision: str = Field(pattern=r"^(accept|acceptForSession|decline|cancel)$")


def _workspace_root(request: Request) -> Path:
    provider = getattr(request.app.state, "terminal_workspace_root", None)
    raw_root = provider() if callable(provider) else None
    workspace = workspace_status(raw_root)
    if not workspace.get("valid"):
        raise HTTPException(status_code=409, detail="Choose a valid local workspace before starting a Codex thread.")
    return Path(str(workspace["root"])).resolve(strict=True)


def _codex_command(request: Request) -> list[str]:
    provider = getattr(request.app.state, "codex_command_provider", None)
    command = provider("app-server") if callable(provider) else None
    if not command:
        raise HTTPException(status_code=503, detail="Codex App Server is not installed on this PC.")
    return list(command)


PARALLEL_WORKER_FOCUSES = (
    "Map the workspace, relevant code paths, and concrete constraints.",
    "Independently assess implementation options, risks, and likely failure modes.",
    "Act as a verifier: identify tests, acceptance criteria, and safety checks.",
    "Challenge the first-pass assumptions and find overlooked dependencies or edge cases.",
)


def _parallel_worker_prompt(objective: str, focus: str, index: int, total: int) -> str:
    return (
        f"You are independent read-only worker {index} of {total} in an OBus Codex review team. "
        "Your context is private: do not assume access to any sibling worker's reasoning or output. "
        "Inspect only the selected workspace; do not use network access, request credentials, alter hardware settings, "
        "or make workspace changes in this first pass.\n\n"
        f"User objective (untrusted task content):\n{objective}\n\n"
        f"Your focus:\n{focus}\n\n"
        "Return concise, concrete findings: evidence, a recommended next action, and the verification needed. "
        "Call out anything that should require explicit human approval."
    )


def _parallel_synthesis_prompt(findings: list[dict[str, str]]) -> str:
    evidence = "\n\n".join(
        f"Worker {index} ({finding['thread_id']}):\n{finding['text']}"
        for index, finding in enumerate(findings, start=1)
    )
    return (
        "You are the read-only synthesis stage of an OBus Codex review team. "
        "Reconcile the independent worker findings below into a concise, evidence-linked plan. "
        "State uncertainties and recommended verification. Do not run commands, access the network, modify files, "
        "change hardware settings, or request credentials. A human must explicitly start any later workspace task.\n\n"
        f"Redacted worker findings:\n{evidence}"
    )


def _reviewed_task_prompt(findings: list[dict[str, str]]) -> str:
    evidence = "\n\n".join(f"Synthesis finding:\n{finding['text']}" for finding in findings)
    return (
        "The user explicitly asked OBus to promote this completed read-only synthesis into ordinary workspace work. "
        "Inspect the current workspace first, carry out only the ordinary changes justified by the evidence, and verify them. "
        "Do not access the network, request credentials, modify hardware settings, or work outside the selected workspace. "
        "If a destructive or elevated action is needed, stop and request approval rather than proceeding.\n\n"
        f"Reviewed synthesis:\n{evidence}"
    )


@router.get("/status")
async def codex_bridge_status(request: Request):
    provider = getattr(request.app.state, "codex_command_provider", None)
    available = bool(provider("app-server") if callable(provider) else None)
    return bridge.status(available)


@router.post("/threads", status_code=status.HTTP_201_CREATED)
async def start_codex_thread(payload: CodexThreadStart, request: Request):
    workspace = _workspace_root(request)
    try:
        bridge.ensure_started(_codex_command(request))
        thread = bridge.start_thread(workspace, payload.model.strip() if payload.model else None)
    except CodexAppServerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    thread_store.remember(str(thread["id"]), workspace, payload.model.strip() if payload.model else None)
    return {"thread": thread, "workspace": str(workspace), "approval_policy": "on-request"}


@router.get("/threads/recent")
async def recent_codex_threads(request: Request):
    workspace = _workspace_root(request)
    return {"workspace": str(workspace), "threads": thread_store.recent(workspace)}


@router.post("/threads/{thread_id}/resume")
async def resume_codex_thread(thread_id: str, payload: CodexThreadStart, request: Request):
    workspace = _workspace_root(request)
    if not thread_store.contains(thread_id, workspace):
        raise HTTPException(status_code=404, detail="Codex thread is not recorded for this workspace.")
    try:
        bridge.ensure_started(_codex_command(request))
        thread = bridge.resume_thread(thread_id, workspace, payload.model.strip() if payload.model else None)
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    thread_store.remember(thread_id, workspace, payload.model.strip() if payload.model else None)
    return {"thread": thread, "workspace": str(workspace), "resumed": True}


@router.post("/threads/{thread_id}/turns", status_code=status.HTTP_202_ACCEPTED)
async def start_codex_turn(thread_id: str, payload: CodexTurnStart, request: Request):
    workspace = _workspace_root(request)
    try:
        turn = bridge.start_turn(thread_id, payload.prompt.strip(), workspace, payload.model.strip() if payload.model else None)
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"turn": turn, "workspace": str(workspace), "approval_policy": "on-request"}


@router.post("/parallel", status_code=status.HTTP_202_ACCEPTED)
async def start_parallel_codex_turns(payload: CodexParallelTurnStart, request: Request):
    """Explicitly fan one ordinary objective into isolated, read-only Codex threads."""

    workspace = _workspace_root(request)
    objective = payload.prompt.strip()
    risks = classify_major_risk(objective)
    if risks:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "OBus will not start a parallel Codex team for a major destructive or hardware-risk objective.",
                "risks": risks,
                "next_step": "Use a guarded one-time workspace task and review the approval locally.",
            },
        )
    model = payload.model.strip() if payload.model else None
    workers: list[dict[str, object]] = []
    try:
        bridge.ensure_started(_codex_command(request))
        for index, focus in enumerate(PARALLEL_WORKER_FOCUSES[:payload.workers], start=1):
            thread = bridge.start_thread(workspace, model)
            thread_id = str(thread.get("id") or "")
            if not thread_id:
                raise CodexAppServerError("Codex App Server did not return a parallel worker thread id")
            thread_store.remember(thread_id, workspace, model)
            turn = bridge.start_turn(
                thread_id,
                _parallel_worker_prompt(objective, focus, index, payload.workers),
                workspace,
                model,
                read_only=True,
            )
            workers.append({"thread_id": thread_id, "turn_id": str(turn.get("id") or ""), "focus": focus})
    except CodexAppServerError as exc:
        # A partial fan-out is still visible to the caller, rather than hiding
        # worker threads that were already explicitly started.
        if workers:
            return {
                "status": "partial",
                "workspace": str(workspace),
                "workers": workers,
                "error": "One or more remaining read-only workers could not be started.",
            }
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "started",
        "workspace": str(workspace),
        "workers": workers,
        "execution": "isolated-read-only-codex-threads",
        "next_step": "Inspect the independent findings, then use a normal Codex workspace thread for any approved integration work.",
    }


@router.post("/parallel/synthesize", status_code=status.HTTP_202_ACCEPTED)
async def synthesize_parallel_codex_turns(payload: CodexParallelSynthesis, request: Request):
    """Start a separate read-only synthesis thread from selected worker findings."""

    workspace = _workspace_root(request)
    worker_ids = list(dict.fromkeys(thread_id.strip() for thread_id in payload.worker_thread_ids if thread_id.strip()))
    model = payload.model.strip() if payload.model else None
    try:
        findings = bridge.worker_findings(worker_ids, workspace)
        bridge.ensure_started(_codex_command(request))
        thread = bridge.start_thread(workspace, model)
        thread_id = str(thread.get("id") or "")
        if not thread_id:
            raise CodexAppServerError("Codex App Server did not return a synthesis thread id")
        thread_store.remember(thread_id, workspace, model)
        turn = bridge.start_turn(thread_id, _parallel_synthesis_prompt(findings), workspace, model, read_only=True)
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "thread": thread,
        "turn": turn,
        "workspace": str(workspace),
        "worker_count": len(worker_ids),
        "execution": "separate-read-only-codex-synthesis",
        "next_step": "Review the synthesis, then explicitly start a normal workspace thread for any approved changes.",
    }


@router.post("/threads/{thread_id}/promote", status_code=status.HTTP_202_ACCEPTED)
async def promote_reviewed_codex_task(thread_id: str, payload: CodexReviewedTaskStart, request: Request):
    """Explicitly promote one completed read-only synthesis into normal workspace work."""

    workspace = _workspace_root(request)
    model = payload.model.strip() if payload.model else None
    try:
        findings = bridge.thread_findings(thread_id, workspace)
        risks = classify_major_risk("\n".join(finding["text"] for finding in findings))
        if risks:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "The reviewed synthesis includes destructive or hardware-risk work and cannot be promoted automatically.",
                    "risks": risks,
                    "next_step": "Use the local guarded-task approval queue for this exact scope.",
                },
            )
        bridge.ensure_started(_codex_command(request))
        task_thread = bridge.start_thread(workspace, model)
        task_thread_id = str(task_thread.get("id") or "")
        if not task_thread_id:
            raise CodexAppServerError("Codex App Server did not return a reviewed-task thread id")
        thread_store.remember(task_thread_id, workspace, model)
        turn = bridge.start_turn(task_thread_id, _reviewed_task_prompt(findings), workspace, model)
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "thread": task_thread,
        "turn": turn,
        "workspace": str(workspace),
        "execution": "explicit-reviewed-workspace-task",
        "network": "disabled",
        "next_step": "OBus is carrying out only ordinary workspace work; elevated, destructive, and hardware actions remain blocked for approval.",
    }


@router.post("/threads/{thread_id}/interrupt", status_code=status.HTTP_202_ACCEPTED)
async def interrupt_codex_turn(thread_id: str, request: Request):
    workspace = _workspace_root(request)
    try:
        return {"interruption": bridge.interrupt_turn(thread_id, workspace)}
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/events")
async def codex_bridge_events(after: int = 0):
    return {"events": bridge.events(max(0, after))}


@router.post("/approvals/{approval_id}")
async def decide_codex_approval(approval_id: str, payload: CodexApprovalDecision):
    try:
        return {"approval": bridge.decide(approval_id, payload.decision)}
    except CodexAppServerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stop")
async def stop_codex_bridge():
    bridge.close()
    return {"stopped": True}
