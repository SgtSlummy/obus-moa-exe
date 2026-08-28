from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from .harness_api import _authorize, runtime
from .voice_runtime import VoiceController

router = APIRouter(
    prefix="/api/harness/voice",
    tags=["harness-voice"],
    dependencies=[Depends(_authorize)],
)
voice_controller = VoiceController(runtime.submit)


class VoiceMute(BaseModel):
    muted: bool


class VoiceListening(BaseModel):
    listening: bool


class VoiceTranscript(BaseModel):
    transcript: str = Field(min_length=1, max_length=50_000)
    workspace: str | None = None
    provider: str = Field(default="codex", pattern=r"^[a-zA-Z0-9_-]+$")
    model: str | None = None


@router.get("/status")
def get_voice_status(request: Request) -> dict[str, object]:
    """Return one truthful local-voice contract for the desktop and harness.

    The harness owns listening and mute state, while the main runtime owns the
    deterministic model resolver used for capture/transcription. Merge them at
    the API boundary so a bundled offline model is neither hidden from the
    desktop nor misrepresented as an environment-only configuration.
    """

    status_payload = voice_controller.status()
    try:
        # Main installs this router during startup, then supplies its canonical
        # local model resolver before this endpoint can receive a request.
        resolver = getattr(request.app.state, "local_voice_status", None)
        if not callable(resolver):
            return status_payload
        local_status = resolver()
    except (AttributeError, ImportError, OSError, RuntimeError):
        return status_payload

    local_ready = bool(local_status.get("ready"))
    status_payload.update({
        "local_ready": local_ready,
        "model_path_configured": bool(local_status.get("model_path_configured")),
        "model_source": local_status.get("model_source"),
        "local_reason": local_status.get("reason"),
        "ready": bool(not status_payload.get("muted") and (local_ready or status_payload.get("cloud_fallback_configured"))),
    })
    return status_payload


@router.patch("/mute")
def set_voice_muted(request: VoiceMute) -> dict[str, object]:
    return voice_controller.set_muted(request.muted)


@router.patch("/listening")
def set_voice_listening(request: VoiceListening) -> dict[str, object]:
    try:
        return voice_controller.set_listening(request.listening)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/transcript", status_code=status.HTTP_202_ACCEPTED)
def submit_voice_transcript(request: VoiceTranscript) -> dict[str, object]:
    try:
        objective_id = voice_controller.submit_transcript(
            request.transcript,
            workspace=request.workspace,
            provider=request.provider,
            model=request.model,
        )
    except (RuntimeError, ValueError) as exc:
        code = status.HTTP_409_CONFLICT if isinstance(exc, RuntimeError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return {"accepted": True, "objective_id": objective_id}
