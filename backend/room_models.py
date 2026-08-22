"""Validated request and public packet models for isolated OBus rooms."""
from __future__ import annotations

import re
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ROOM_MODES = {"collaborative", "adversarial"}
ROOM_STATUSES = {"idle", "running", "complete", "blocked", "failed", "archived"}
MAX_ROOM_CARDS = 10
MAX_FORUM_ROOMS = 20
MAX_PACKET_TEXT = 4000


_SECRET_PATTERNS = (
    (re.compile(r"(?i)(api[_ -]?key|access[_ -]?token|authorization|bearer|password|secret)\s*[:=]\s*\S+"), r"\1: [REDACTED]"),
    (re.compile(r"\b(?:sk|gh[pousr]|xox[baprs])_[A-Za-z0-9_-]{12,}\b"), "[REDACTED]"),
)


def sanitize_public_text(value: Any, limit: int = MAX_PACKET_TEXT) -> str:
    text = str(value or "")
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"(?is)(?:hidden|private)\s+(?:prompt|transcript|messages?)\s*:\s*.*", "[PRIVATE CONTEXT REDACTED]", text)
    return text.strip()[:limit]


def sanitize_public_list(value: Any, limit: int = 30) -> list[str]:
    if not isinstance(value, list):
        return []
    return [sanitize_public_text(item, 500) for item in value[:limit] if str(item).strip()]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoomCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    card_ids: List[str] = Field(min_length=1, max_length=MAX_ROOM_CARDS)
    mode: str = "collaborative"
    chymeria_card_id: Optional[str] = None
    chymeria_key_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Room name cannot be empty")
        return value

    @field_validator("card_ids")
    @classmethod
    def unique_cards(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("card_ids must be unique")
        if any(not item.strip() for item in value):
            raise ValueError("card_ids cannot contain empty values")
        return value

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        if value not in ROOM_MODES:
            raise ValueError("mode must be collaborative or adversarial")
        return value


class RoomUpdate(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    card_ids: Optional[List[str]] = Field(default=None, min_length=1, max_length=MAX_ROOM_CARDS)
    mode: Optional[str] = None
    chymeria_card_id: Optional[str] = None
    chymeria_key_id: Optional[str] = None
    archived: Optional[bool] = None

    @field_validator("card_ids")
    @classmethod
    def unique_updated_cards(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("card_ids must be unique")
        return value

    @field_validator("mode")
    @classmethod
    def valid_updated_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ROOM_MODES:
            raise ValueError("mode must be collaborative or adversarial")
        return value


class RoomRunRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=12000)
    rag_enabled: bool = True

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt cannot be empty")
        return value


class DecisionPacket(StrictModel):
    room_id: str
    revision: int = Field(ge=1)
    position: str = Field(min_length=1, max_length=MAX_PACKET_TEXT)
    confidence: str = "medium"
    rationale: str = Field(default="", max_length=MAX_PACKET_TEXT)
    evidence_refs: List[str] = Field(default_factory=list, max_length=30)
    unresolved_questions: List[str] = Field(default_factory=list, max_length=30)
    requested_responses: List[str] = Field(default_factory=list, max_length=30)
    status: str = "provisional"


class ForumThreadCreate(StrictModel):
    title: str = Field(min_length=1, max_length=160)
    prompt: str = Field(min_length=1, max_length=12000)
    room_ids: List[str] = Field(min_length=2, max_length=MAX_FORUM_ROOMS)

    @field_validator("title", "prompt")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be empty")
        return value

    @field_validator("room_ids")
    @classmethod
    def unique_rooms(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("room_ids must be unique")
        return value


class ForumMessageCreate(StrictModel):
    room_id: str
    kind: str = "question"
    body: str = Field(min_length=1, max_length=MAX_PACKET_TEXT)
    reply_to: Optional[str] = None

    @field_validator("body")
    @classmethod
    def clean_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("body cannot be empty")
        return value
