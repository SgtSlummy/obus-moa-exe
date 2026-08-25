"""Tailscale-constrained, signed peer API for Thor and Loki nodes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.harness_api import runtime
from backend.peer_sync import PeerSyncStore, is_tailscale_address

router = APIRouter(prefix="/api/peers", tags=["peers"])
peer_store = PeerSyncStore(runtime.store.path)


class PairRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    public_key: str = Field(min_length=40, max_length=128)
    pairing_key: str = Field(min_length=8, max_length=1024)


class SignedEnvelope(BaseModel):
    peer_id: str = Field(min_length=32, max_length=64)
    timestamp: int
    nonce: str = Field(min_length=16, max_length=128)
    payload: dict[str, Any]
    signature: str = Field(min_length=40, max_length=256)


def _tailscale_only(request: Request) -> str:
    address = request.client.host if request.client else ""
    if not is_tailscale_address(address):
        raise HTTPException(status_code=403, detail="peer API requires loopback or Tailscale")
    return address


def _verify(envelope: SignedEnvelope) -> dict[str, Any]:
    try:
        return peer_store.verify(envelope.peer_id, envelope.timestamp, envelope.nonce,
                                 envelope.payload, envelope.signature)
    except (KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/identity")
def peer_identity(request: Request):
    _tailscale_only(request)
    return peer_store.identity_public()


@router.post("/pair", status_code=201)
def pair_peer(payload: PairRequest, request: Request):
    _tailscale_only(request)
    try:
        return peer_store.pair(payload.name.strip(), payload.public_key, payload.pairing_key)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
def list_peers(request: Request):
    _tailscale_only(request)
    return {"peers": peer_store.peers()}


@router.delete("/{peer_id}")
def revoke_peer(peer_id: str, request: Request):
    _tailscale_only(request)
    try:
        return peer_store.revoke(peer_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="peer not found") from exc


@router.post("/tasks", status_code=202)
def submit_peer_task(envelope: SignedEnvelope, request: Request):
    _tailscale_only(request)
    peer = _verify(envelope)
    payload = envelope.payload
    objective = str(payload.get("objective") or "").strip()
    if not objective:
        raise HTTPException(status_code=422, detail="objective is required")
    workspace = payload.get("workspace")
    from pathlib import Path
    path = Path(str(workspace)).expanduser() if workspace else Path.cwd()
    try:
        return runtime.submit(objective, path, source=f"peer:{peer['id']}",
                              priority=int(payload.get("priority", 50)),
                              max_attempts=int(payload.get("max_attempts", 3)),
                              provider=str(payload.get("provider", "codex")),
                              model=payload.get("model"))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/sync/lessons")
def sync_peer_lessons(envelope: SignedEnvelope, request: Request):
    _tailscale_only(request)
    _verify(envelope)
    lessons = envelope.payload.get("lessons") or []
    if not isinstance(lessons, list) or len(lessons) > 1000:
        raise HTTPException(status_code=422, detail="lessons must be a list of at most 1000 items")
    results = []
    for lesson in lessons:
        if not isinstance(lesson, dict):
            raise HTTPException(status_code=422, detail="each lesson must be an object")
        try:
            results.append(peer_store.ingest_lesson(lesson, envelope.signature))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"results": results}


@router.get("/sync/lessons")
def list_synced_lessons(request: Request):
    _tailscale_only(request)
    return {"lessons": peer_store.synced_lessons()}
