"""Memory schema types for the Obus memory system.

Defines the core data structures for memory items including:
- MemoryType: Classification of memory contents
- MemoryScope: Visibility and lifetime boundaries
- MemoryItem: Primary data container with metadata
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class MemoryType(str, Enum):
    """Classification of memory item type.
    
    Working: Short-lived state for current turn
    Episodic: Summaries of past events/conversations
    Semantic: Stable facts and preferences
    Procedural: Reusable workflows and procedures
    Decision: Project/team decisions and rationale
    Summary: Compacted conversation history
    """
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    DECISION = "decision"
    SUMMARY = "summary"


class MemoryScope(str, Enum):
    """Scope boundaries for memory visibility and persistence.
    
    Global: System-wide preferences and defaults
    User: Personal preferences and individual facts
    Project: Project-specific facts, decisions, and procedures
    Session: Turn-local short-term state
    """
    GLOBAL = "global"
    USER = "user"
    PROJECT = "project"
    SESSION = "session"


@dataclass
class MemoryItem:
    """Primary memory container with intelligent metadata.

    Memory items are the atomic unit of the Obus memory system.
    They support automatic lifecycle management, confidence scoring,
    and rich metadata for provenance tracking.
    """
    id: str
    content: str
    memory_type: MemoryType
    scope: MemoryScope
    summary: str = ""
    source: str = "manual"
    importance: float = 0.5
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None

    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())
        if not isinstance(self.content, str):
            self.content = str(self.content)

    def update_timestamp(self):
        """Update the updatedAt timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()


def memory_item_from_dict(data: dict[str, Any]) -> MemoryItem:
    """Create MemoryItem from dict, handling camelCase aliases."""
    memory_type = MemoryType(data.get("type", data.get("memory_type", "semantic")))
    scope = MemoryScope(data.get("scope", "project"))

    return MemoryItem(
        id=data["id"],
        content=data["content"],
        memory_type=memory_type,
        scope=scope,
        summary=data.get("summary", ""),
        source=data.get("source", "manual"),
        importance=data.get("importance", 0.5),
        confidence=data.get("confidence", 0.5),
        created_at=data.get("created_at", data.get("createdAt", datetime.now(timezone.utc).isoformat())),
        updated_at=data.get("updated_at", data.get("updatedAt", datetime.now(timezone_utc).isoformat())),
        expires_at=data.get("expires_at", data.get("expiresAt")),
        project_id=data.get("project_id"),
        session_id=data.get("session_id"),
        user_id=data.get("user_id"),
        metadata=data.get("metadata", {}),
    )