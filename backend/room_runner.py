"""Room-local AgentCouncil execution with a public Chymeria packet."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from backend.room_council import build_card_prompt, build_chymeria_prompt, build_room_council_plan
from backend.room_models import DecisionPacket, sanitize_public_list, sanitize_public_text


class RoomRuntimeError(RuntimeError):
    pass


OFFLINE_ROOM_KEY = {
    "id": "key-offline-room",
    "name": "Offline deterministic planner",
    "provider": "offline",
    "model": "offline-deterministic-planner",
    "max_context_tokens": 32768,
    "local": True,
    "state": "ready",
}


def offline_room_complete(**kwargs) -> str:
    """Return an honest, deterministic room record when no model provider exists."""
    phase = kwargs["phase"]
    card = kwargs.get("card", {})
    prompt = " ".join(str(kwargs.get("prompt", "")).split())[:240]
    position = f"Offline planning mode: {phase} recorded for {card.get('name', 'room seat')} on '{prompt}'. Configure a provider for model-generated reasoning."
    payload = {
        "position": position,
        "confidence": "low",
        "rationale": "No model provider is configured; this is a deterministic execution record, not a model answer.",
        "evidence_refs": [],
        "unresolved_questions": ["Configure a provider to generate model-based analysis."],
        "requested_responses": [],
        "status": "offline",
    }
    if phase == "triage":
        payload["leader_id"] = card.get("id")
    return json.dumps(payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_output(raw: str, phase: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except (TypeError, ValueError):
        pass
    return {
        "position": str(raw).strip() or f"No {phase} position returned",
        "confidence": "low",
        "rationale": "The model returned unstructured text; preserved as a provisional position.",
        "evidence_refs": [],
        "unresolved_questions": [],
        "requested_responses": [],
        "status": "provisional",
    }


def _assignment_for(card: dict[str, Any], room: dict[str, Any], state: dict[str, Any], provider_status: Callable[[dict], bool]) -> dict[str, Any]:
    requested = card.get("assigned_key_id") if card.get("assignment_mode") == "manual" else None
    requested = requested or room.get("chymeria", {}).get("key_id")
    keys = list(state.get("keys", []))
    if requested == OFFLINE_ROOM_KEY["id"]:
        keys.append(OFFLINE_ROOM_KEY)
    candidates = [key for key in keys if key.get("state") == "ready" and provider_status(key)]
    if requested:
        chosen = next((key for key in candidates if key.get("id") == requested), None)
        if not chosen:
            raise RoomRuntimeError(f"Requested room Key is not ready and connected or supported: {requested}")
    else:
        chosen = candidates[0] if candidates else None
    if not chosen:
        raise RoomRuntimeError("No ready and connected Solomon's Key is available for this room")
    return {
        "llm_key": chosen["id"],
        "provider": chosen.get("name", chosen.get("provider", "unknown")),
        "model": chosen.get("model", ""),
        "max_context_tokens": chosen.get("max_context_tokens", 131072),
    }


def run_room_council(
    room: dict[str, Any],
    state: dict[str, Any],
    prompt: str,
    complete: Callable[..., str],
    provider_status: Callable[[dict], bool],
    forum_packets: list[dict[str, Any]] | None = None,
    on_message: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    prompt = sanitize_public_text(prompt, 4000)
    cards_by_id = {card["id"]: card for card in state.get("cards", [])}
    cards = [cards_by_id[card_id] for card_id in room.get("card_ids", []) if card_id in cards_by_id]
    if not cards:
        raise RoomRuntimeError("Room has no valid Tarot seats")
    plan = build_room_council_plan(room, prompt)
    assignments = {card["id"]: _assignment_for(card, room, state, provider_status) for card in cards}
    private_messages: list[dict[str, Any]] = []
    outputs: list[str] = []
    chymeria_card_id = room.get("chymeria", {}).get("card_id") or cards[0]["id"]

    def emit(message: dict[str, Any]) -> None:
        private_messages.append(message)
        if on_message:
            on_message(dict(message))

    def call(phase: str, card: dict[str, Any], request_prompt: str) -> str:
        raw = complete(
            room=room, card=card, assignment=assignments[card["id"]], phase=phase,
            prompt=request_prompt, forum_packets=forum_packets or [],
        )
        parsed = _parse_output(raw, phase)
        emit({
            "id": "rm-" + hashlib.sha256(f"{room['id']}:{len(private_messages)}:{phase}".encode()).hexdigest()[:16],
            "room_id": room["id"], "visibility": "room", "author_type": "card" if card["id"] != chymeria_card_id else "chymeria",
            "author_id": card["id"], "phase": phase, "body": sanitize_public_text(parsed.get("position", ""), 1200), "created_at": _now(),
        })
        return json.dumps(parsed, ensure_ascii=False)

    def call_parallel(phase: str, phase_cards: list[dict[str, Any]], prompt_for_card: Callable[[dict[str, Any]], str]) -> list[str]:
        """Run independent room-seat proposals concurrently and publish in seat order.

        The execution is parallel, while transcript ordering stays deterministic for
        humans, tests, and downstream Chymeria synthesis. Each seat receives only
        its scoped room prompt; no hidden reasoning or credentials are collected.
        """
        def complete_card(card: dict[str, Any]) -> dict[str, Any]:
            raw = complete(
                room=room, card=card, assignment=assignments[card["id"]], phase=phase,
                prompt=prompt_for_card(card), forum_packets=forum_packets or [],
            )
            return _parse_output(raw, phase)

        if len(phase_cards) == 1:
            parsed_outputs = [complete_card(phase_cards[0])]
        else:
            workers = min(int(plan["max_parallel"]), len(phase_cards))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="obus-room-seat") as executor:
                parsed_outputs = list(executor.map(complete_card, phase_cards))

        serialized = []
        for card, parsed_output in zip(phase_cards, parsed_outputs):
            emit({
                "id": "rm-" + hashlib.sha256(f"{room['id']}:{len(private_messages)}:{phase}".encode()).hexdigest()[:16],
                "room_id": room["id"], "visibility": "room", "author_type": "card" if card["id"] != chymeria_card_id else "chymeria",
                "author_id": card["id"], "phase": phase, "body": sanitize_public_text(parsed_output.get("position", ""), 1200), "created_at": _now(),
            })
            serialized.append(json.dumps(parsed_output, ensure_ascii=False))
        return serialized

    if plan["short_circuit"]:
        chymeria = cards_by_id.get(chymeria_card_id, cards[0])
        raw = complete(
            room=room, card=chymeria, assignment=assignments[chymeria["id"]], phase="direct",
            prompt=build_chymeria_prompt(room, "direct", prompt, [], forum_packets), forum_packets=forum_packets or [],
        )
        parsed = _parse_output(raw, "direct")
        emit({"id": "rm-" + hashlib.sha256(f"{room['id']}:direct".encode()).hexdigest()[:16], "room_id": room["id"], "visibility": "room", "author_type": "chymeria", "author_id": chymeria["id"], "phase": "direct", "body": sanitize_public_text(parsed.get("position", ""), 1200), "created_at": _now()})
    elif plan["mode"] == "collaborative":
        drafts = call_parallel("draft", cards, lambda card: build_card_prompt(room, card, "draft", prompt))
        improved = call_parallel("improve", cards, lambda card: build_card_prompt(room, card, "improve", prompt, drafts))
        outputs = improved
        chymeria = cards_by_id.get(chymeria_card_id, cards[0])
        raw = complete(room=room, card=chymeria, assignment=assignments[chymeria["id"]], phase="synthesize", prompt=build_chymeria_prompt(room, "synthesize", prompt, improved, forum_packets), forum_packets=forum_packets or [])
        parsed = _parse_output(raw, "synthesize")
        emit({"id": "rm-" + hashlib.sha256(f"{room['id']}:synthesize:{len(private_messages)}".encode()).hexdigest()[:16], "room_id": room["id"], "visibility": "room", "author_type": "chymeria", "author_id": chymeria["id"], "phase": "synthesize", "body": sanitize_public_text(parsed.get("position", ""), 1200), "created_at": _now()})
    else:
        drafts = call_parallel("draft", cards, lambda card: build_card_prompt(room, card, "draft", prompt))
        chymeria = cards_by_id.get(chymeria_card_id, cards[0])
        triage_raw = complete(
            room=room, card=chymeria, assignment=assignments[chymeria["id"]], phase="triage",
            prompt=build_chymeria_prompt(room, "triage", prompt, drafts, forum_packets), forum_packets=forum_packets or [],
        )
        triage = _parse_output(triage_raw, "triage")
        emit({"id": "rm-" + hashlib.sha256(f"{room['id']}:triage:{len(private_messages)}".encode()).hexdigest()[:16], "room_id": room["id"], "visibility": "room", "author_type": "chymeria", "author_id": chymeria["id"], "phase": "triage", "body": sanitize_public_text(triage.get("position", "Triage complete"), 1200), "created_at": _now()})
        leader_id = triage.get("leader_id") if triage.get("leader_id") in {card["id"] for card in cards} else cards[0]["id"]
        leader_index = next(index for index, card in enumerate(cards) if card["id"] == leader_id)
        leader = drafts[leader_index]
        attackers = [card for card in cards if card["id"] != leader_id]
        attacks = call_parallel("attack", attackers, lambda card: build_card_prompt(room, card, "attack", prompt, [leader])) if attackers else []
        outputs = attacks or drafts
        raw = complete(room=room, card=chymeria, assignment=assignments[chymeria["id"]], phase="verdict", prompt=build_chymeria_prompt(room, "verdict", prompt, [leader] + attacks, forum_packets), forum_packets=forum_packets or [])
        parsed = _parse_output(raw, "verdict")
        emit({"id": "rm-" + hashlib.sha256(f"{room['id']}:verdict:{len(private_messages)}".encode()).hexdigest()[:16], "room_id": room["id"], "visibility": "room", "author_type": "chymeria", "author_id": chymeria["id"], "phase": "verdict", "body": sanitize_public_text(parsed.get("position", ""), 1200), "created_at": _now()})

    revision = int(room.get("revision", 0)) + 1
    packet_data = {
        "room_id": room["id"], "revision": revision,
        "position": sanitize_public_text(parsed.get("position", "No decision")),
        "confidence": sanitize_public_text(parsed.get("confidence", "low"), 32),
        "rationale": sanitize_public_text(parsed.get("rationale", "")),
        "evidence_refs": sanitize_public_list(parsed.get("evidence_refs", [])),
        "unresolved_questions": sanitize_public_list(parsed.get("unresolved_questions", [])),
        "requested_responses": sanitize_public_list(parsed.get("requested_responses", [])),
        "status": sanitize_public_text(parsed.get("status", "provisional"), 32),
    }
    packet = DecisionPacket.model_validate(packet_data).model_dump()
    room["revision"] = revision
    room["status"] = "complete"
    room["last_packet"] = packet
    room["updated_at"] = _now()
    return {"room": room, "plan": plan, "decision_packet": packet, "private_messages": private_messages, "assignments": assignments}
