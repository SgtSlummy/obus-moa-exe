"""Forum storage helpers for room Chymeria decision packets."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from backend.room_models import sanitize_public_list, sanitize_public_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def packet_identity(thread_id: str, packet: dict[str, Any]) -> str:
    raw = json.dumps({"thread_id": thread_id, "room_id": packet.get("room_id"), "revision": packet.get("revision"), "position": packet.get("position")}, sort_keys=True)
    return "fmsg-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def public_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "room_id": packet.get("room_id"), "revision": packet.get("revision"),
        "position": sanitize_public_text(packet.get("position")),
        "confidence": sanitize_public_text(packet.get("confidence"), 32),
        "rationale": sanitize_public_text(packet.get("rationale")),
        "evidence_refs": sanitize_public_list(packet.get("evidence_refs")),
        "unresolved_questions": sanitize_public_list(packet.get("unresolved_questions")),
        "requested_responses": sanitize_public_list(packet.get("requested_responses")),
        "status": sanitize_public_text(packet.get("status"), 32),
    }


def append_packet_message(thread: dict[str, Any], packet: dict[str, Any], room: dict[str, Any]) -> dict[str, Any] | None:
    public = public_packet(packet)
    message_id = packet_identity(thread["id"], public)
    if any(message.get("id") == message_id for message in thread.get("messages", [])):
        return None
    message = {
        "id": message_id,
        "thread_id": thread["id"],
        "room_id": room["id"],
        "author_type": "chymeria",
        "author_id": room.get("chymeria", {}).get("card_id"),
        "kind": "decision",
        "body": public["position"],
        "packet": public,
        "reply_to": None,
        "thread_revision": int(thread.get("revision", 0)) + 1,
        "created_at": _now(),
    }
    thread.setdefault("messages", []).append(message)
    thread["revision"] = message["thread_revision"]
    thread["updated_at"] = message["created_at"]
    return message


def append_question_message(thread: dict[str, Any], request: dict[str, Any], room: dict[str, Any]) -> dict[str, Any]:
    message = {
        "id": "fmsg-" + hashlib.sha256(f"{thread['id']}:{len(thread.get('messages', []))}:{request['body']}".encode()).hexdigest()[:20],
        "thread_id": thread["id"], "room_id": room["id"], "author_type": "chymeria",
        "author_id": room.get("chymeria", {}).get("card_id"), "kind": request.get("kind", "question"),
        "body": sanitize_public_text(request["body"]), "packet": None, "reply_to": request.get("reply_to"),
        "thread_revision": int(thread.get("revision", 0)) + 1, "created_at": _now(),
    }
    thread.setdefault("messages", []).append(message)
    thread["revision"] = message["thread_revision"]
    thread["last_round_signature"] = None
    thread["updated_at"] = message["created_at"]
    return message
