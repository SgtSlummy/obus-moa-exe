"""Authenticated, in-memory LAN audio relay used by the Voice Link test page."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse


router = APIRouter(tags=["voice-link"])
_ROOM_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")


class VoiceLinkRooms:
    """A bounded room registry; it stores no recordings and relays only live chunks."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, room: str, socket: WebSocket) -> None:
        async with self._lock:
            self._rooms[room].add(socket)

    async def leave(self, room: str, socket: WebSocket) -> None:
        async with self._lock:
            peers = self._rooms.get(room)
            if peers is None:
                return
            peers.discard(socket)
            if not peers:
                self._rooms.pop(room, None)

    async def relay(self, room: str, sender: WebSocket, audio: bytes) -> int:
        """Forward one browser audio chunk to current peers, dropping failed peers."""
        if not audio or len(audio) > 1_000_000:
            return 0
        async with self._lock:
            recipients = tuple(peer for peer in self._rooms.get(room, ()) if peer is not sender)
        delivered = 0
        for peer in recipients:
            try:
                await peer.send_bytes(audio)
                delivered += 1
            except RuntimeError:
                await self.leave(room, peer)
        return delivered


voice_link_rooms = VoiceLinkRooms()


def _shared_key() -> str:
    return os.environ.get("OBUS_VOICE_LINK_KEY", "").strip()


def _valid_join(payload: str) -> str | None:
    try:
        message = json.loads(payload)
    except json.JSONDecodeError:
        return None
    room = message.get("room") if isinstance(message, dict) else None
    key = message.get("key") if isinstance(message, dict) else None
    if not isinstance(room, str) or not _ROOM_RE.fullmatch(room):
        return None
    if not isinstance(key, str) or not _shared_key() or not hmac.compare_digest(key, _shared_key()):
        return None
    return room


def _assistant_join(payload: str) -> bool:
    try:
        message = json.loads(payload)
    except json.JSONDecodeError:
        return False
    return bool(isinstance(message, dict) and message.get("assistant") is True)


@router.get("/voice-link", include_in_schema=False)
def voice_link_page(request: Request):
    if not _shared_key():
        raise HTTPException(status_code=503, detail="Set OBUS_VOICE_LINK_KEY before using Voice Link.")
    return FileResponse(Path(__file__).parent / "static" / "voice_link.html", media_type="text/html")


@router.websocket("/api/voice-link/stream")
async def voice_link_stream(socket: WebSocket) -> None:
    await socket.accept()
    room: str | None = None
    assistant_mode = False
    try:
        first_message = await asyncio.wait_for(socket.receive_text(), timeout=15)
        room = _valid_join(first_message)
        if room is None:
            await socket.close(code=1008, reason="Voice Link requires a valid room and shared key.")
            return
        assistant_mode = _assistant_join(first_message)
        await voice_link_rooms.join(room, socket)
        await socket.send_text(json.dumps({"type": "joined", "room": room}))
        while True:
            message = await socket.receive()
            if message["type"] == "websocket.disconnect":
                break
            audio = message.get("bytes")
            if audio is not None:
                if assistant_mode:
                    processor = getattr(socket.app.state, "voice_link_process", None)
                    if not callable(processor):
                        await socket.send_text(json.dumps({"type": "voice.error", "message": "Voice processing is unavailable."}))
                        continue
                    try:
                        result = await asyncio.to_thread(processor, audio)
                        await socket.send_text(json.dumps({"type": "voice.task", **result}))
                    except (RuntimeError, ValueError) as exc:
                        await socket.send_text(json.dumps({"type": "voice.error", "message": str(exc)}))
                else:
                    await voice_link_rooms.relay(room, socket, audio)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if room is not None:
            await voice_link_rooms.leave(room, socket)
