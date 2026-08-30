from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend
from backend.voice_link_api import VoiceLinkRooms, _valid_join


class Socket:
    def __init__(self): self.sent: list[bytes] = []
    async def send_bytes(self, value: bytes): self.sent.append(value)


def test_voice_link_requires_configured_shared_key(monkeypatch):
    monkeypatch.delenv("OBUS_VOICE_LINK_KEY", raising=False)
    assert _valid_join('{"room":"test-room","key":"x"}') is None
    monkeypatch.setenv("OBUS_VOICE_LINK_KEY", "shared-test-key")
    assert _valid_join('{"room":"test-room","key":"shared-test-key"}') == "test-room"
    assert _valid_join('{"room":"bad room","key":"shared-test-key"}') is None


def test_voice_link_relays_only_to_room_peers():
    async def exercise():
        rooms, sender, peer, elsewhere = VoiceLinkRooms(), Socket(), Socket(), Socket()
        await rooms.join("one", sender)
        await rooms.join("one", peer)
        await rooms.join("two", elsewhere)
        assert await rooms.relay("one", sender, b"audio") == 1
        assert peer.sent == [b"audio"]
        assert sender.sent == [] and elsewhere.sent == []
    asyncio.run(exercise())


def test_voice_link_page_and_websocket_relay(monkeypatch):
    monkeypatch.setenv("OBUS_VOICE_LINK_KEY", "shared-test-key")
    with TestClient(backend.app) as client:
        assert client.get("/voice-link").status_code == 200
        with client.websocket_connect("/api/voice-link/stream") as first, client.websocket_connect("/api/voice-link/stream") as second:
            first.send_text('{"room":"test-room","key":"shared-test-key"}')
            second.send_text('{"room":"test-room","key":"shared-test-key"}')
            assert first.receive_json() == {"type": "joined", "room": "test-room"}
            assert second.receive_json() == {"type": "joined", "room": "test-room"}
            first.send_bytes(b"audio")
            assert second.receive_bytes() == b"audio"


def test_voice_link_page_uses_push_to_talk():
    page = (Path(__file__).resolve().parents[1] / "backend" / "static" / "voice_link.html").read_text(encoding="utf-8")
    assert 'id="talk"' in page
    assert "pointerdown" in page and "pointerup" in page
    assert "recorder.pause()" in page


def test_assistant_join_requires_explicit_true_flag():
    from backend.voice_link_api import _assistant_join
    assert _assistant_join('{"assistant":true}') is True
    assert _assistant_join('{"assistant":false}') is False


def test_assistant_mode_processes_audio_and_returns_spoken_task_payload(monkeypatch):
    monkeypatch.setenv("OBUS_VOICE_LINK_KEY", "shared-test-key")
    monkeypatch.setattr(backend.app.state, "voice_link_process", lambda audio: {"transcript": audio.decode(), "task_id": "task-123"})
    with TestClient(backend.app) as client, client.websocket_connect("/api/voice-link/stream") as socket:
        socket.send_text('{"room":"test-room","key":"shared-test-key","assistant":true}')
        assert socket.receive_json() == {"type": "joined", "room": "test-room"}
        socket.send_bytes(b"hello")
        assert socket.receive_json() == {"type": "voice.task", "transcript": "hello", "task_id": "task-123"}
