"""Unit tests for memory schema types and data structures."""
import unittest
from datetime import datetime


class TestMemoryType(unittest.TestCase):
    def test_memory_type_enum_members(self):
        """Test MemoryType enum values."""
        from backend.memory_schema import MemoryType
        
        self.assertEqual(MemoryType.WORKING.value, "working")
        self.assertEqual(MemoryType.EPISODIC.value, "episodic")
        self.assertEqual(MemoryType.SEMANTIC.value, "semantic")
        self.assertEqual(MemoryType.PROCEDURAL.value, "procedural")
        self.assertEqual(MemoryType.DECISION.value, "decision")
        self.assertEqual(MemoryType.SUMMARY.value, "summary")


class TestMemoryScope(unittest.TestCase):
    def test_memory_scope_enum_members(self):
        """Test MemoryScope enum values."""
        from backend.memory_schema import MemoryScope
        
        self.assertEqual(MemoryScope.GLOBAL.value, "global")
        self.assertEqual(MemoryScope.USER.value, "user")
        self.assertEqual(MemoryScope.PROJECT.value, "project")
        self.assertEqual(MemoryScope.SESSION.value, "session")


class TestMemoryItem(unittest.TestCase):
    def test_memory_item_creation_with_required_fields(self):
        """Test MemoryItem dataclass creation with required fields."""
        from backend.memory_schema import MemoryItem, MemoryType, MemoryScope
        
        item = MemoryItem(
            id="test_001",
            content="Obus prioritizes low token usage",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.PROJECT
        )
        
        self.assertEqual(item.id, "test_001")
        self.assertEqual(item.memory_type, MemoryType.SEMANTIC)
        self.assertEqual(item.scope, MemoryScope.PROJECT)
        self.assertEqual(item.importance, 0.5)  # default
        self.assertEqual(item.confidence, 0.5)  # default

    def test_memory_item_with_all_fields(self):
        """Test MemoryItem creation with all optional fields."""
        from backend.memory_schema import MemoryItem, MemoryType, MemoryScope
        import uuid
        
        item = MemoryItem(
            id=f"test_{uuid.uuid4().hex[:8]}",
            content="User prefers Claude-based plans",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.USER,
            importance=0.85,
            confidence=0.95,
            source="automatic",
            metadata={"project": "obus", "version": "1.0"}
        )
        
        self.assertEqual(item.memory_type, MemoryType.SEMANTIC)
        self.assertEqual(item.scope, MemoryScope.USER)
        self.assertEqual(item.importance, 0.85)
        self.assertEqual(item.confidence, 0.95)
        self.assertEqual(item.source, "automatic")
        self.assertIn("project", item.metadata)


if __name__ == "__main__":
    unittest.main()