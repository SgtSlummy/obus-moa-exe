# Obus Memory System Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate a layered memory system into Obus to improve functionality, reduce response time, and lower token usage through intelligent context management.

**Architecture:** Implement a 5-layer memory architecture (working, episodic, semantic, procedural, relational) with async extraction/retrieval pipelines, token-budgeted context packing, and file-backed memory packs inspired by Claude Mythos.

**Tech Stack:** SQLite + FTS5/BM25, vector embeddings (sqlite-vss or Chroma), async job queues, markdown/YAML for human-editable memory packs.

---

## Current Context & Assumptions

- Obus is an AI agent framework currently operating statelessly or with minimal context management
- Primary pain points: high token usage on long conversations, slow response times due to large context windows, lack of persistent memory across sessions
- The system likely has a core agent loop, tool execution, and LLM calling infrastructure
- We assume a Python or TypeScript codebase with modular architecture

## Research Summary

Based on my earlier research, these are research-informed patterns / candidate projects to validate:

| Source | Key Insight | Obus Application |
|---|---|---|
| aiagentmemory.org/how-to-give-llm-memory | Layered memory architectures | 5-layer memory model |
| anshug/claude-mythos | File-backed memory packs, conversation management | `.obus/memory/` markdown packs |
| Mem0 | Automatic memory extraction, user preferences | Async extraction pipeline |
| Zep | Session summaries, fast retrieval | Rolling session compaction |
| Letta/MemGPT | Working vs archival memory separation | Context window budgeting |
| Graphiti | Temporal knowledge graphs | Entity relationship tracking (Phase 6) |

---

## Proposed Memory Model

### 1. Working Memory (Immediate Context)
- Current task state, constraints, open questions
- Always included but compact (100-300 tokens)
- Storage: In-process memory

### 2. Episodic Memory (Conversation Summaries)
- Prior conversation summaries, decisions, outcomes
- Retrieved only when relevant (200-600 tokens)
- Storage: SQLite table with FTS index

### 3. Semantic Memory (Stable Facts)
- User preferences, project facts, architectural decisions
- Retrieved by relevance and scope (200-500 tokens)
- Storage: SQLite table, optional embeddings

### 4. Procedural Memory (Reusable Workflows)
- Human-editable markdown files with step-by-step procedures
- Loaded based on task type
- Example: "How to run computer-use doctor"

### 5. Graph/Relational Memory (Optional)
- Entity relationships (User → Project → Tool → Issue)
- Phase 6 enhancement

---

## Implementation Phases

### Phase 1: Memory Layer Foundation (Week 1-2)

**Objective:** Establish persistent storage, schemas, and basic CRUD operations.

#### Task 1.1: Define MemoryItem Schema

**Files:**
- Create: `src/memory/schema.py`
- Create: `tests/memory/test_schema.py`

**TDD Cycle:**

1. **Write failing test:**
```python
# tests/memory/test_schema.py
from src.memory.schema import MemoryItem, MemoryScope, MemoryType

def test_memory_item_creation():
    item = MemoryItem(
        id="test_001",
        content="Obus prioritizes low token usage",
        memory_type=MemoryType.SEMANTIC,
        scope=MemoryScope.PROJECT,
        importance=0.8,
        metadata={"project": "obus"}
    )
    assert item.id == "test_001"
    assert item.memory_type == MemoryType.SEMANTIC
```

2. **Run test:** `pytest tests/memory/test_schema.py -v` → FAIL

3. **Write minimal implementation:** (see plan file)

4. **Run test:** PASS

5. **Commit:** `git commit -m "feat: add MemoryItem schema and types"`

#### Task 1.2: Initialize SQLite Memory Database

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/memory/test_store.py`

TDD cycle for MemoryStore with create/read/update/delete operations.

#### Task 1.3: Add Basic Search and Scope Filtering

**Files:**
- Modify: `src/memory/store.py`
- Create: `tests/memory/test_search.py`

TDD cycle for FTS5 search with scope filtering.

---

### Phase 2: Session Summaries (Week 3)

**Objective:** Implement rolling session summaries to compact old conversations.

#### Task 2.1: Create Summary Service

**Files:**
- Create: `src/memory/summarizer.py`
- Create: `tests/memory/test_summarizer.py`

TDD cycle for SessionSummarizer class with sliding window and compaction.

#### Task 2.2: Integrate with Agent Loop

**Files:**
- Modify: `src/agent/loop.py` or discovery result

Add summary injection before LLM call.

---

### Phase 3: Vector Retrieval (Week 4-5)

**Objective:** Add semantic search via embeddings.

#### Task 3.1: Add Embedding Generation

**Files:**
- Create: `src/memory/embeddings.py`
- Modify: `src/memory/store.py`

Support local and API embeddings, add upsert_with_embedding method.

#### Task 3.2: Hybrid Search

**Files:**
- Modify: `src/memory/store.py`

Combine BM25 and vector similarity scores.

#### Task 3.3: Token-Budgeted Context Packing

**Files:**
- Create: `src/memory/packer.py`

Token budget utility to pack memories under limit.

---

### Phase 4: Automatic Memory Writes (Week 6-7)

**Objective:** Extract and store memories automatically after each turn.

**Architecture:**
```
After LLM response:
  1. Queue extraction job (non-blocking)
  2. Background worker: classify → score → deduplicate → commit
```

**Files:**
- Create: `src/memory/extractor.py`
- Create: `src/memory/queue.py`
- Modify: `src/agent/loop.py`

**Write Criteria (never write):**
- Transient instructions, low confidence (<0.6), secrets/PII, duplicates

---

### Phase 5: File-Backed Memory Packs (Week 8)

**Objective:** Add Claude Mythos-inspired editable markdown packs.

**Files:**
- Create: `src/memory/packs.py`
- Create: `.obus/memory/user.md`
- Create: `.obus/memory/project.md`
- Create: `.obus/memory/procedures.md`
- Create: `.obus/memory/decisions.md`

**Templates include:**
- User preferences, timezone, active projects
- Project tech stack, coding standards
- Reusable workflows, decisions log

---

### Phase 6: Graph/Temporal Memory (Optional, Week 9+)

**Files:**
- Create: `src/memory/graph.py`
- Create: `src/memory/entity_tracker.py`

Track entity relationships with temporal validity.

---

## Integration Points

**Likely files to modify (to be confirmed in Phase 1 discovery):**
- `src/agent/loop.py` or `src/agent/orchestrator.py`
- `src/config/settings.py`
- `src/cli.py` or `src/main.py`
- Agent loop entry points

**New directories:**
```
src/memory/
  schema.py  store.py  summarizer.py  embeddings.py
  packer.py  extractor.py  queue.py  packs.py  graph.py

tests/memory/
  test_schema.py  test_store.py  test_search.py
  test_summarizer.py  test_embeddings.py  test_packer.py
  test_extractor.py  test_packs.py
```

---

## Testing & Validation

**Unit Tests:** TDD cycle for each module
**Integration Tests:** Memory retrieval → LLM context → response flow
**Performance Benchmarks:**
- Target: 40-60% token reduction on long conversations
- Target: 15-30% faster response time

**Validation Commands:**
```bash
pytest tests/memory/ -v --cov=src/memory
python -m obus memory search "token usage"
obus memory add --scope project "Obus prioritizes low token usage"
```

---

## Success Criteria

1. **Token Reduction:** 40-60% on conversations >10 turns
2. **Response Time:** 15-30% faster user-perceived
3. **Memory Accuracy:** >90% relevant memories in top-5
4. **Zero Blocking:** Never increase LLM latency
5. **Developer Experience:** Editable packs, clear CLI

---

## Immediate Next Steps

1. Explore Obus codebase structure (confirm Python/TypeScript, ORM, agent loop)
2. Set up `src/memory/` and `tests/memory/` directories
3. Begin Phase 1, Task 1.1 with full TDD cycle