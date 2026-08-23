"""SQLite memory store with FTS5 search for memory persistence."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.memory_schema import MemoryItem, MemoryType, MemoryScope


class MemoryStore:
    """SQLite-backed persistent store for MemoryItems with FTS5 full-text search."""
    
    def __init__(self, db_path: Path):
        """Initialize the memory store, creating tables if needed.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create memories table and FTS5 index if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Main memories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT,
                    source TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            
            # FTS5 virtual table for fast keyword search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(id UNINDEXED, content, summary, type UNINDEXED, scope UNINDEXED, 
                          tokenize='porter')
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def _item_to_tuple(self, item: MemoryItem) -> tuple:
        """Convert MemoryItem to database row tuple."""
        import json
        return (
            item.id,
            item.memory_type.value,
            item.scope.value,
            item.content,
            item.summary,
            item.source,
            item.importance,
            item.confidence,
            item.created_at if isinstance(item.created_at, str) else item.created_at.isoformat(),
            item.updated_at if isinstance(item.updated_at, str) else item.updated_at.isoformat(),
            item.expires_at,
            json.dumps(item.metadata) if item.metadata else '{}'
        )
    
    def add(self, item: MemoryItem) -> bool:
        """Add a memory item to the store.
        
        Args:
            item: The MemoryItem to add
            
        Returns:
            True if successful, False otherwise
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            # Insert into main table
            conn.execute("""
                INSERT OR REPLACE INTO memories 
                (id, type, scope, content, summary, source, importance, confidence, 
                 created_at, updated_at, expires_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._item_to_tuple(item))
            
            # Sync to FTS index
            conn.execute("""
                INSERT OR REPLACE INTO memories_fts(rowid, id, content, summary, type, scope)
                SELECT rowid, id, content, summary, type, scope FROM memories WHERE id = ?
            """, (item.id,))
            
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by ID.
        
        Args:
            item_id: The unique identifier
            
        Returns:
            MemoryItem if found, None otherwise
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (item_id,)
            ).fetchone()
            conn.close()
            
            if not row:
                return None
            
            return MemoryItem(
                id=row[0],
                content=row[3],
                memory_type=MemoryType(row[1]),
                scope=MemoryScope(row[2]) if row[2] else MemoryScope.PROJECT,
                summary=row[4] or "",
                source=row[5] or "manual",
                importance=row[6],
                confidence=row[7],
                createdAt=row[8],
                updatedAt=row[9],
                expiresAt=row[10],
                metadata=json.loads(row[11]) if row[11] else {}
            )
        except Exception:
            return None
        finally:
            conn.close()
    
    def update(self, item_id: str, **kwargs) -> bool:
        """Update fields of an existing memory item.
        
        Args:
            item_id: The unique identifier
            **kwargs: Fields to update (importance, confidence, content, metadata, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not kwargs:
            return False
        
        # Build SET clause from kwargs
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [item_id]
        
        conn = sqlite3.connect(self.db_path)
        try:
            # Update main table
            conn.execute(f"""
                UPDATE memories SET {set_clause}, updated_at = ?
                WHERE id = ?
            """, values + [datetime.now(timezone.utc).isoformat(), item_id])
            
            if conn.total_changes == 0:
                return False
            
            # Sync to FTS
            conn.execute("""
                INSERT OR REPLACE INTO memories_fts(rowid, id, content, summary, type, scope)
                SELECT rowid, id, content, summary, type, scope FROM memories WHERE id = ?
            """, (item_id,))
            
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def delete(self, item_id: str) -> bool:
        """Delete a memory item by ID.
        
        Args:
            item_id: The unique identifier
            
        Returns:
            True if deleted, False if not found
        """
        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute(
                "DELETE FROM memories WHERE id = ?", (item_id,)
            )
            conn.execute("DELETE FROM memories_fts WHERE rowid NOT IN (SELECT rowid FROM memories)")
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()
    
    def search(self, query: str, limit: int = 50) -> list[MemoryItem]:
        """Search memory items using FTS5 full-text search.
        
        Args:
            query: Search terms
            limit: Maximum number of results
            
        Returns:
            List of matching MemoryItems
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """SELECT id, content, type, scope, summary, source, importance, confidence,
                          created_at, updated_at, expires_at, metadata_json
                   FROM memories_fts 
                   WHERE memories_fts MATCH ? 
                   LIMIT ?""",
                (query, limit)
            ).fetchall()
            conn.close()
            
            results = []
            for row in rows:
                try:
                    item = MemoryItem(
                        id=row[0],
                        content=row[1],
                        memory_type=MemoryType(row[2]),
                        scope=MemoryScope(row[3]),
                        summary=row[4] or "",
                        source=row[5] or "manual",
                        importance=row[6],
                        confidence=row[7],
                        createdAt=row[8],
                        updatedAt=row[9],
                        expiresAt=row[10],
                        metadata=json.loads(row[11]) if row[11] else {}
                    )
                    results.append(item)
                except Exception:
                    continue
            
            return results
        except Exception:
            return []
        finally:
            conn.close()
    
    def list_by_scope(self, scope: MemoryScope, limit: int = 100) -> list[MemoryItem]:
        """List all memory items for a given scope.
        
        Args:
            scope: The scope to filter by
            limit: Maximum number of results
            
        Returns:
            List of MemoryItems
        """
        import json
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM memories WHERE scope = ? ORDER BY created_at DESC LIMIT ?",
                (scope.value, limit)
            ).fetchall()
            
            results = []
            for row in rows:
                try:
                    item = MemoryItem(
                        id=row[0],
                        content=row[3],
                        memory_type=MemoryType(row[1]),
                        scope=MemoryScope(row[2]) if row[2] else MemoryScope.PROJECT,
                        summary=row[4] or "",
                        source=row[5] or "manual",
                        importance=row[6],
                        confidence=row[7],
                        created_at=row[8],
                        updated_at=row[9],
                        expires_at=row[10],
                        metadata=json.loads(row[11]) if row[11] else {}
                    )
                    results.append(item)
                except Exception:
                    continue
            
            return results
        finally:
            conn.close()
    
    def clear_all(self) -> int:
        """Delete all memory items (useful for testing).
        
        Returns:
            Number of items deleted
        """
        conn = sqlite3.connect(self.db_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            conn.execute("DELETE FROM memories")
            conn.execute("DELETE FROM memories_fts")
            conn.commit()
            return count
        finally:
            conn.close()