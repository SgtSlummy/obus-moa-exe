"""SQLite persistence and full-text search for structured memory items."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.memory_schema import MemoryItem, MemoryScope, MemoryType


class MemoryStore:
    """Persist :class:`MemoryItem` records in SQLite with an FTS5 index."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_tables(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    importance REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    project_id TEXT,
                    session_id TEXT,
                    user_id TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(id UNINDEXED, content, summary, tokenize='porter')
                """
            )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _serialize_item(item: MemoryItem) -> tuple[object, ...]:
        return (
            item.id,
            item.memory_type.value,
            item.scope.value,
            item.content,
            item.summary,
            item.source,
            item.importance,
            item.confidence,
            json.dumps(item.metadata, sort_keys=True),
            item.created_at,
            item.updated_at,
            item.expires_at,
            item.project_id,
            item.session_id,
            item.user_id,
        )

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            scope=MemoryScope(row["scope"]),
            summary=row["summary"],
            source=row["source"],
            importance=row["importance"],
            confidence=row["confidence"],
            metadata=json.loads(row["metadata_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
        )

    @staticmethod
    def _sync_fts(connection: sqlite3.Connection, item_id: str) -> None:
        row = connection.execute(
            "SELECT rowid, id, content, summary FROM memories WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return
        connection.execute("DELETE FROM memories_fts WHERE rowid = ?", (row["rowid"],))
        connection.execute(
            "INSERT INTO memories_fts(rowid, id, content, summary) VALUES (?, ?, ?, ?)",
            (row["rowid"], row["id"], row["content"], row["summary"]),
        )

    def add(self, item: MemoryItem) -> bool:
        """Create or replace a memory item and update its full-text index."""
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id, memory_type, scope, content, summary, source, importance,
                    confidence, metadata_json, created_at, updated_at, expires_at,
                    project_id, session_id, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    memory_type = excluded.memory_type,
                    scope = excluded.scope,
                    content = excluded.content,
                    summary = excluded.summary,
                    source = excluded.source,
                    importance = excluded.importance,
                    confidence = excluded.confidence,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at,
                    project_id = excluded.project_id,
                    session_id = excluded.session_id,
                    user_id = excluded.user_id
                """,
                self._serialize_item(item),
            )
            self._sync_fts(connection, item.id)
        return True

    def get(self, item_id: str) -> MemoryItem | None:
        """Return a memory item by ID, or ``None`` when it does not exist."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?", (item_id,)
            ).fetchone()
        return self._row_to_item(row) if row is not None else None

    def update(self, item_id: str, **changes: Any) -> bool:
        """Apply supported field updates to a memory item and reindex it."""
        if not changes:
            return False

        columns = {
            "memory_type": "memory_type",
            "scope": "scope",
            "content": "content",
            "summary": "summary",
            "source": "source",
            "importance": "importance",
            "confidence": "confidence",
            "metadata": "metadata_json",
            "expires_at": "expires_at",
            "project_id": "project_id",
            "session_id": "session_id",
            "user_id": "user_id",
        }
        unknown_fields = set(changes) - set(columns)
        if unknown_fields:
            raise ValueError(f"Unsupported memory fields: {sorted(unknown_fields)}")

        assignments: list[str] = []
        values: list[Any] = []
        for field, value in changes.items():
            if field in {"memory_type", "scope"} and isinstance(value, (MemoryType, MemoryScope)):
                value = value.value
            elif field == "metadata":
                value = json.dumps(value, sort_keys=True)
            assignments.append(f"{columns[field]} = ?")
            values.append(value)

        assignments.append("updated_at = ?")
        values.append(self._timestamp())
        values.append(item_id)

        with self._connection() as connection:
            result = connection.execute(
                f"UPDATE memories SET {', '.join(assignments)} WHERE id = ?", values
            )
            if result.rowcount == 0:
                return False
            self._sync_fts(connection, item_id)
        return True

    def delete(self, item_id: str) -> bool:
        """Remove a memory item and its matching FTS entry."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT rowid FROM memories WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM memories_fts WHERE rowid = ?", (row["rowid"],))
            connection.execute("DELETE FROM memories WHERE id = ?", (item_id,))
        return True

    def search(self, query: str, limit: int = 50) -> list[MemoryItem]:
        """Return up to ``limit`` items whose content or summary matches ``query``."""
        if not query.strip() or limit <= 0:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT memories.*
                FROM memories_fts
                JOIN memories ON memories.rowid = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY bm25(memories_fts)
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def list_by_scope(self, scope: MemoryScope, limit: int = 100) -> list[MemoryItem]:
        """List recent memory items within a scope."""
        if limit <= 0:
            return []
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE scope = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (scope.value, limit),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def clear_all(self) -> int:
        """Remove every item and return the number removed."""
        with self._connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            connection.execute("DELETE FROM memories_fts")
            connection.execute("DELETE FROM memories")
        return count
