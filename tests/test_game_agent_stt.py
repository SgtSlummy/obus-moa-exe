"""Scoped private game-agent STT regression coverage."""

from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import game_agent as agent


WAV_FIXTURE = (
    b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (16_000).to_bytes(4, "little")
    + (32_000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
    + b"data" + (0).to_bytes(4, "little")
)


def _headers(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    return {"X-Obus-Game-Token": agent.token()}


def _scoped_payload():
    return {
        "contract": "raph-obus-game-stt-v1",
        "scope": {"campaign": "campaign-1", "owner": "host-1", "role": "host"},
        "session": "session-1",
        "requestId": "request-1",
        "runtime": {
            "contract": "raph-obus-game-runtime-v1",
            "bootEpoch": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "sessionPolicyRevision": 1,
        },
        "audio_base64": base64.b64encode(WAV_FIXTURE).decode("ascii"),
        "mime_type": "audio/wav",
    }


def test_legacy_audio_only_request_is_rejected_before_model_dispatch(tmp_path, monkeypatch):
    called = False

    def local_transcribe(_audio: bytes):
        nonlocal called
        called = True
        return "unexpected", "unexpected"

    monkeypatch.setattr(agent, "_transcribe_game_audio", local_transcribe)
    headers = _headers(tmp_path, monkeypatch)
    legacy_payload = {"audio_base64": base64.b64encode(WAV_FIXTURE).decode("ascii"), "mime_type": "audio/wav"}

    with TestClient(agent.app) as client:
        response = client.post("/api/voice/transcribe", headers=headers, json=legacy_payload)

    assert response.status_code == 400
    assert called is False


def test_scoped_stt_requires_active_runtime_authority_before_model_dispatch(tmp_path, monkeypatch):
    called = False

    def local_transcribe(_audio: bytes):
        nonlocal called
        called = True
        return "unexpected", "unexpected"

    monkeypatch.setattr(agent, "_transcribe_game_audio", local_transcribe)
    headers = _headers(tmp_path, monkeypatch)

    with TestClient(agent.app) as client:
        response = client.post("/api/voice/transcribe", headers=headers, json=_scoped_payload())
        capabilities = client.get("/api/game/capabilities", headers=headers)

    assert response.status_code == 409
    assert "runtime_host_generation_required" in response.json()["detail"]
    assert called is False
    assert capabilities.json()["local_stt"]["runtime_envelope_required"] is True
    assert capabilities.json()["local_stt"]["route_ready"] is False


def test_scoped_stt_rejects_invalid_runtime_fence_before_dispatch(tmp_path, monkeypatch):
    called = False

    def local_transcribe(_audio: bytes):
        nonlocal called
        called = True
        return "unexpected", "unexpected"

    payload = _scoped_payload()
    payload["runtime"]["generation"] = "not-a-uuid"
    monkeypatch.setattr(agent, "_transcribe_game_audio", local_transcribe)
    headers = _headers(tmp_path, monkeypatch)

    with TestClient(agent.app) as client:
        response = client.post("/api/voice/transcribe", headers=headers, json=payload)

    assert response.status_code == 400
    assert called is False


def test_scoped_stt_replays_only_an_identical_private_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setattr(agent, "RUNTIME", None)
    authority = agent.runtime_authority()
    runtime = authority.register(
        {
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "campaign-1",
            "session": "session-1",
            "generation": str(uuid.uuid4()),
            "expectedBootEpoch": authority.boot_epoch,
            "expectedGeneration": None,
            "opId": str(uuid.uuid4()),
            "leaseSeconds": 30,
        }
    )["runtime"]
    payload = _scoped_payload()
    payload["runtime"] = {key: runtime[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}
    calls: list[bytes] = []

    def local_transcribe(audio: bytes):
        calls.append(audio)
        return "private transcript", "test-model"

    monkeypatch.setattr(agent, "_transcribe_game_audio", local_transcribe)
    first = agent._transcribe_scoped_stt(payload, WAV_FIXTURE)
    second = agent._transcribe_scoped_stt(payload, WAV_FIXTURE)
    assert first == second
    assert calls == [WAV_FIXTURE]
    assert first["receipt"]["retention"] == {"raw_audio_persisted": False, "request_evidence_persisted": False, "general_memory_writes": False, "route_journal_writes": False, "game_receipt_persisted": True, "transcript_persisted_in_game_receipt": True}
    with pytest.raises(HTTPException, match="STT request ID conflict"):
        agent._transcribe_scoped_stt(payload, WAV_FIXTURE + b"different")


def test_master_policy_change_during_stt_cannot_commit_a_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "ROOT", tmp_path)
    monkeypatch.setattr(agent, "RUNTIME", None)
    authority = agent.runtime_authority()
    runtime = authority.register(
        {
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "campaign-1",
            "session": "session-1",
            "generation": str(uuid.uuid4()),
            "expectedBootEpoch": authority.boot_epoch,
            "expectedGeneration": None,
            "opId": str(uuid.uuid4()),
            "leaseSeconds": 30,
        }
    )["runtime"]
    payload = _scoped_payload()
    payload["runtime"] = {key: runtime[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}

    def local_transcribe(_audio: bytes):
        authority.patch_policy(
            {
                "contract": "raph-obus-game-runtime-v1",
                "campaign": "campaign-1",
                "session": "session-1",
                "generation": payload["runtime"]["generation"],
                "expectedBootEpoch": payload["runtime"]["bootEpoch"],
                "expectedSessionPolicyRevision": payload["runtime"]["sessionPolicyRevision"],
                "opId": str(uuid.uuid4()),
                "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
            }
        )
        return "late transcript", "test-model"

    monkeypatch.setattr(agent, "_transcribe_game_audio", local_transcribe)
    with pytest.raises(HTTPException, match="runtime_fence_stale"):
        agent._transcribe_scoped_stt(payload, WAV_FIXTURE)
    with agent.database() as db:
        assert db.execute("SELECT 1 FROM stt_jobs").fetchone() is None


def test_transcribe_game_audio_removes_transient_wav_and_uses_cpu_int8(tmp_path, monkeypatch):
    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "model.bin").write_bytes(b"model")
    (model_path / "config.json").write_text("{}", encoding="utf-8")
    observed: list[Path] = []
    constructor_options: list[dict[str, object]] = []

    class Segment:
        text = " synthetic speech "

    class FakeModel:
        def __init__(self, *_args, **kwargs):
            constructor_options.append(kwargs)

        def transcribe(self, audio_path, **_kwargs):
            observed.append(Path(audio_path))
            assert Path(audio_path).is_file()
            return [Segment()], object()

    monkeypatch.setattr(agent, "local_stt_status", lambda: {"ready": True})
    monkeypatch.setattr(agent, "_game_stt_model_path", lambda: model_path)
    monkeypatch.setattr(agent, "STT_MODEL", None)
    monkeypatch.setattr(agent, "STT_MODEL_PATH", "")
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeModel))

    transcript, model = agent._transcribe_game_audio(WAV_FIXTURE)

    assert transcript == "synthetic speech"
    assert model == "model"
    assert constructor_options == [{"device": "cpu", "compute_type": "int8"}]
    assert observed and not observed[0].exists()
