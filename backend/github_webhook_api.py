from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from .github_webhooks import (
    MAX_WEBHOOK_BYTES,
    GitHubWebhookStore,
    decode_payload,
    repair_request,
    verify_github_signature,
)
from .harness_api import _authorize, runtime

router = APIRouter(prefix="/api/integrations/github-app", tags=["github-app"])
_store: GitHubWebhookStore | None = None


def webhook_store() -> GitHubWebhookStore:
    global _store
    if _store is None:
        _store = GitHubWebhookStore()
    return _store


def _objective_id(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("id") or result.get("objective_id") or "")
    return str(getattr(result, "id", result))


@router.get("/webhook/status", dependencies=[Depends(_authorize)])
def github_webhook_status() -> dict[str, Any]:
    return webhook_store().status()


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(request: Request) -> dict[str, Any]:
    secret = os.getenv("OBUS_GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub webhook secret is not configured")

    body = await request.body()
    if len(body) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="GitHub webhook payload is too large")
    if not verify_github_signature(secret, body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub webhook signature")

    delivery_id = request.headers.get("X-GitHub-Delivery", "").strip()
    event = request.headers.get("X-GitHub-Event", "").strip()
    if not delivery_id or len(delivery_id) > 128 or not event or len(event) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid GitHub delivery headers")
    try:
        payload = decode_payload(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    store = webhook_store()
    if not store.record(delivery_id, event, payload):
        return {"accepted": True, "duplicate": True, "delivery_id": delivery_id}

    objective_id: str | None = None
    prompt = repair_request(event, payload)
    auto_repair = os.getenv("OBUS_GITHUB_AUTO_REPAIR", "").lower() in {"1", "true", "yes"}
    if prompt and auto_repair:
        result = runtime.submit(
            prompt,
            Path(os.getenv("OBUS_WORKSPACE", Path.cwd())),
            source="github-webhook",
            priority=80,
            provider="codex",
            model=None,
        )
        objective_id = _objective_id(result)
        if objective_id:
            store.attach_objective(delivery_id, objective_id)

    return {
        "accepted": True,
        "duplicate": False,
        "delivery_id": delivery_id,
        "event": event,
        "repair_objective_id": objective_id,
    }
