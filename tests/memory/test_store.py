"""Unit tests for SQLite memory store with FTS5 search."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.memory_schema import MemoryItem, MemoryType, MemoryScope


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_memory.db"

    def tearDown(self):
        """Clean up test database."""
        import shutil
        if self.db_path.exists():
            self.db_path.unlink()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_creates_tables_on_init(self):
        """Test that init creates memories and memories_fts tables."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        conn = sqlite3.connect(self.db_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        
        self.assertIn("memories", tables)
        self.assertIn("memories_fts", tables)

    def test_add_memory_item(self):
        """Test adding a MemoryItem to the store."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        item = MemoryItem(
            id="test_001",
            content="Obus prioritizes low token usage",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.PROJECT,
            importance=0.8
        )
        
        result = store.add(item)
        self.assertTrue(result)
        
        retrieved = store.get("test_001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, item.content)

    def test_get_memory_by_id(self):
        """Test retrieving a memory item by ID."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        item = MemoryItem(
            id="test_002",
            content="User prefers concrete plans",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.USER
        )
        store.add(item)
        
        retrieved = store.get("test_002")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test_002")
        self.assertEqual(retrieved.scope, MemoryScope.USER)

    def test_update_memory_item(self):
        """Test updating an existing memory item."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        item = MemoryItem(
            id="test_003",
            content="Original content",
            memory_type=MemoryType.EPISODIC,
            scope=MemoryScope.SESSION
        )
        store.add(item)
        
        store.update("test_003", importance=0.9)
        
        updated = store.get("test_003")
        self.assertEqual(updated.importance, 0.9)

    def test_delete_memory_item(self):
        """Test deleting a memory item by ID."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        item = MemoryItem(
            id="test_004",
            content="To be deleted",
            memory_type=MemoryType.WORKING,
            scope=MemoryScope.SESSION
        )
        store.add(item)
        
        result = store.delete("test_004")
        self.assertTrue(result)
        
        retrieved = store.get("test_004")
        self.assertIsNone(retrieved)

    def test_search_by_keyword(self):
        """Test keyword search in memory content."""
        from backend.memory_store import MemoryStore
        
        store = MemoryStore(self.db_path)
        
        items = [
            MemoryItem(id="s1", content="token usage optimization", 
                        memory_type=MemoryType.SEMANTIC, scope=MemoryScope.PROJECT),
            MemoryItem(id="s2", content="response time measurement", 
                        memory_type=MemoryType.EPISODIC, scope=MemoryScope.SESSION),
            MemoryItem(id="s3", content="user preference settings", 
                        memory_type=MemoryType.SEMANTIC, scope=MemoryScope.USER),
        ]
        for item in items:
            store.add(item)
        
        results = store.search("token usage")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "s1")


if __name__ == "__main__":
    unittest.main()