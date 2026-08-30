from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
    provider: str = Field(default="autoagent", pattern=r"^[a-zA-Z0-9_-]+$")
    model: str | None = None


@router.get("/status")
def get_voice_status() -> dict[str, object]:
    return voice_controller.status()


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
