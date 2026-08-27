"""Loopback-only Flow Studio API and guarded harness handoff."""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .execution_policy import classify_major_risk
from .flow_studio import FlowClone, FlowCreate, FlowDocument, FlowStore, ProposalApply, compile_runtime_objective
from .harness_api import runtime as harness_runtime

api_router = APIRouter(prefix="/api/flow-studio", tags=["flow-studio"])
page_router = APIRouter(tags=["flow-studio"])
flow_store = FlowStore()

def _local(request: Request) -> None:
    host = (request.client.host if request.client else "").split("%",1)[0].lower()
    if host not in {"127.0.0.1","::1","localhost","testclient"}: raise HTTPException(403,"Flow Studio is local-only")
def _failure(exc: Exception) -> HTTPException: return HTTPException(403 if isinstance(exc,PermissionError) else 409 if isinstance(exc,RuntimeError) else 422,str(exc))
class FlowRun(BaseModel):
    workspace: str | None = Field(default=None,max_length=1000)
    priority: int = Field(default=50,ge=0,le=100)
    max_attempts: int = Field(default=1,ge=1,le=3)
    provider: str = Field(default="codex",pattern="^(codex|ollama|openai-compatible)$")
    model: str | None = Field(default=None,max_length=256)

@page_router.get("/flow-studio",include_in_schema=False)
def page(request: Request): _local(request); return FileResponse(Path(__file__).parent / "static" / "flow_studio.html",media_type="text/html")
@api_router.get("/flows")
def list_flows(request: Request): _local(request); return {"flows":flow_store.list()}
@api_router.post("/flows",status_code=status.HTTP_201_CREATED)
def create(payload: FlowCreate,request: Request): _local(request); return flow_store.create(payload.title.strip())
@api_router.get("/flows/{flow_id}")
def get(flow_id: str,request: Request):
    _local(request)
    try:return flow_store.get(flow_id)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
@api_router.post("/flows/{flow_id}/clone",status_code=status.HTTP_201_CREATED)
def clone(flow_id: str,payload: FlowClone,request: Request):
    _local(request)
    try:return flow_store.clone(flow_id,payload.title.strip() if payload.title else None)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
@api_router.put("/flows/{flow_id}")
def update(flow_id: str,payload: FlowDocument,request: Request):
    _local(request)
    try:return flow_store.update(flow_id,payload)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
    except Exception as exc:raise _failure(exc) from exc
@api_router.post("/flows/{flow_id}/validate")
def validate(flow_id: str,request: Request):
    _local(request)
    try:return flow_store.validate(flow_id)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
    except Exception as exc:raise _failure(exc) from exc
@api_router.post("/flows/{flow_id}/proposals/split-research-agent")
def proposal(flow_id: str,request: Request):
    _local(request)
    try:return flow_store.propose_split(flow_id)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
    except Exception as exc:raise _failure(exc) from exc
@api_router.post("/flows/{flow_id}/proposals/split-research-agent/apply")
def apply(flow_id: str,payload: ProposalApply,request: Request):
    _local(request)
    try:return flow_store.apply_split(flow_id,payload.base_version)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
    except Exception as exc:raise _failure(exc) from exc
@api_router.post("/flows/{flow_id}/run",status_code=status.HTTP_202_ACCEPTED)
def run(flow_id: str,payload: FlowRun,request: Request):
    _local(request)
    try:flow,validation=flow_store.get(flow_id),flow_store.validate(flow_id)
    except KeyError as exc:raise HTTPException(404,"Flow not found") from exc
    if flow.get("kind") != "draft":raise HTTPException(409,"Copy a built-in template before running it.")
    if not validation["valid"]:raise HTTPException(422,{"message":"Fix graph errors before running","errors":validation["errors"]})
    objective=compile_runtime_objective(flow);risks=classify_major_risk(objective)
    if risks:raise HTTPException(409,{"message":"Flow Studio cannot bypass the local approval queue. Open Runtime and create the one-time guarded task there.","risks":risks})
    try:workspace=(Path(payload.workspace).expanduser() if payload.workspace else Path.cwd()).resolve(strict=True)
    except (OSError,RuntimeError) as exc:raise HTTPException(400,"Flow workspace must already exist") from exc
    if not workspace.is_dir():raise HTTPException(400,"Flow workspace must be a directory")
    task=harness_runtime.submit(objective,workspace,"local-flow-studio",payload.priority,payload.max_attempts,payload.provider,payload.model)
    return {"flow_id":flow_id,"flow_version":flow["version"],"task":task,"major_risks":risks}
