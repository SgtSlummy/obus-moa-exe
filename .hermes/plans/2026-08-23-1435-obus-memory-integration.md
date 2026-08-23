# Obus Memory System Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate a layered memory system into Obus to improve functionality, reduce response time, and lower token usage through intelligent context management.

**Architecture:** Implement a 5-layer memory architecture (working, episodic, semantic, procedural, relational) with async extraction/retrieval pipelines, token-budgeted context packing, and file-backed memory packs inspired by Claude Mythos.

**Tech Stack:** SQLite + FTS5/BM25, vector embeddings (sqlite-vss or Chroma), async job queues, markdown/YAML for human-editable memory packs.

---

## Current Context & Assumptions

- Obus is an AI agent framework operating with minimal context management
- Primary pain points: high token usage on long conversations, slow responses due to large context windows, lack of persistent memory
- Based on workspace exploration, Obus has:
  - `src/` directory structure
  - `tests/` with pytest
  - `backend/` module (card_routing, memory_hub, solomon_seals)
  - `obus_mcp_server.py`, `obus_hermes_bridge.py`
  - Python-based codebase
- Research-informed patterns from: Claude Memory Utils, Mem0, Zep, Letta, LangMem, Graphiti

---

## Proposed Memory Model

### 1. Working Memory (Immediate Context)
Current task state, constraints, open questions. Always included but compact (100-300 tokens).

### 2. Episodic Memory (Conversation Summaries)
Prior conversation summaries, decisions, task outcomes. Retrieved when relevant (200-600 tokens).

### 3. Semantic Memory (Stable Facts)
User preferences, project facts, architectural decisions. Retrieved by relevance (200-500 tokens).

### 4. Procedural Memory (Reusable Workflows)
Human-editable markdown files with step-by-step procedures. Loaded based on task type.

### 5. Graph/Relational Memory (Optional)
Entity relationships (User → Project → Tool → Issue). Phase 6 enhancement.

---

## Implementation Phases

### Phase 1: Memory Layer Foundation (Week 1-2)
Establish persistent storage, schemas, and basic CRUD.

#### Task 1.1: Create MemoryItem Schema
**Objective:** Define dataclasses for memory items with 5-layer model.

**Files:**
- Create: `src/memory/schema.py`
- Create: `tests/memory/test_schema.py`

**TDD Steps:**
1. Write test for MemoryItem creation with all required fields
2. Run test: `pytest tests/memory/test_schema.py -v` → FAIL
3. Implement MemoryItem, MemoryType, MemoryScope enums
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add MemoryItem schema with 5-layer model"`

#### Task 1.2: Initialize SQLite Memory Database
**Objective:** Add persistent storage with FTS5 for keyword search.

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/memory/test_store.py`

**TDD Steps:**
1. Write test for store CRUD operations
2. Run test → FAIL
3. Implement MemoryStore class with add/get/update/delete
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add SQLite memory store with FTS5"`

#### Task 1.3: Add Full-Text Search
**Objective:** Enable keyword search with scope filtering.

**Files:**
- Modify: `src/memory/store.py`
- Create: `tests/memory/test_search.py`

**TDD Steps:**
1. Write test for search returning relevant memories by scope
2. Run test → FAIL
3. Implement search() method joining memories + memories_fts
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add FTS5 search with scope filtering"`

---

### Phase 2: Token Budgeting & Retrieval (Week 3)
Prevent memory context from inflating prompt size.

#### Task 2.1: Add Token Budget Utility
**Objective:** Estimate tokens and pack memories under budget.

**Files:**
- Create: `src/memory/packer.py`
- Create: `tests/memory/test_packer.py`

**TDD Steps:**
1. Write test for budget enforcement (only top memories included)
2. Run test → FAIL
3. Implement estimate_tokens() and pack_under_budget()
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add token-budgeted memory packer"`

#### Task 2.2: Create Memory Retriever
**Objective:** Retrieve relevant memories with ranking and budget enforcement.

**Files:**
- Create: `src/memory/retriever.py`
- Create: `tests/memory/test_retriever.py`

**TDD Steps:**
1. Write test for relevance-based memory retrieval
2. Run test → FAIL
3. Implement Retriever class that ranks by importance/recency
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add memory retriever with ranking"`

---

### Phase 3: Session Summaries (Week 4)
Compact old conversations to reduce prompt size.

#### Task 3.1: Add Rolling Summarizer
**Objective:** Summarize old turns when conversation grows.

**Files:**
- Create: `src/memory/summarizer.py`
- Create: `tests/memory/test_summarizer.py`

**TDD Steps:**
1. Write test for turn compaction when exceeding threshold
2. Run test → FAIL
3. Implement SessionSummarizer with extractive baseline (no LLM call)
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add session summarizer for turn compaction"`

---

### Phase 4: File-Backed Memory Packs (Week 5)
Add Claude Mythos-inspired transparent memory files.

#### Task 4.1: Create Memory Pack Templates
**Objective:** Provide editable markdown files for user/project context.

**Files:**
- Create: `src/memory/packs.py`
- Create: `.obus/memory/user.md` (template)
- Create: `.obus/memory/project.md` (template)
- Create: `.obus/memory/procedures.md` (template)

**TDD Steps:**
1. Write test for pack file initialization
2. Run test → FAIL
3. Implement initialize_packs() and section parser
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add file-backed memory pack templates"`

---

### Phase 5: Async Memory Writes (Week 6)
Extract memories after response, not blocking LLM path.

#### Task 5.1: Add Memory Extractor
**Objective:** Identify durable facts vs transient instructions.

**Files:**
- Create: `src/memory/extractor.py`
- Create: `tests/memory/test_extractor.py`

**TDD Steps:**
1. Write tests for classification rules (preferences, facts, decisions)
2. Run tests → FAIL
3. Implement extract_candidates() with rule-based filtering
4. Run tests → PASS
5. Commit: `git commit -m "feat(memory): add rule-based memory extractor"`

#### Task 5.2: Add Write Queue
**Objective:** Non-blocking memory writes after LLM response.

**Files:**
- Create: `src/memory/queue.py`
- Modify: `backend/memory_hub.py` or equivalent
- Create: `tests/memory/test_queue.py`

**TDD Steps:**
1. Write test for async write queue
2. Run test → FAIL
3. Implement background job for memory extraction
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add async memory write queue"`

---

### Phase 6: Vector Search (Week 7)
Add semantic search via embeddings.

#### Task 6.1: Add Embedding Provider
**Objective:** Support local and API embeddings.

**Files:**
- Create: `src/memory/embeddings.py`
- Create: `tests/memory/test_embeddings.py`

**TDD Steps:**
1. Write test for embedding generation interface
2. Run test → FAIL
3. Implement EmbeddingProvider abstraction
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add embedding provider abstraction"`

#### Task 6.2: Hybrid Search
**Objective:** Combine BM25 + vector similarity with token budget.

**Files:**
- Modify: `src/memory/retriever.py`
- Modify: `src/memory/packer.py`
- Create: `tests/memory/test_hybrid_search.py`

**TDD Steps:**
1. Write test for hybrid retrieval
2. Run test → FAIL
3. Implement similarity fusion with token budget
4. Run test → PASS
5. Commit: `git commit -m "feat(memory): add hybrid BM25+vector search"`

---

### Phase 7: Integration & CLI (Week 8)
Connect memory system to Obus runtime and add commands.

#### Task 7.1: Integrate with Agent Loop
**Objective:** Inject memory before LLM call, queue write after.

**Files:**
- Modify: `backend/deck_router.py` or `obus_hermes_bridge.py`
- Create: `tests/integration/test_memory_integration.py`

**TDD Steps:**
1. Write integration test for memory injection
2. Run test → FAIL
3. Add memory retrieval call before LLM invocation
4. Add async write queue after response
5. Run test → PASS
6. Commit: `git commit -m "integr(m): connect memory system to agent loop"`

#### Task 7.2: Add Memory CLI
**Objective:** Allow users to inspect/manage memory.

**Files:**
- Modify: `obus_launcher.py` or create `scripts/memory_cli.py`
- Create: `tests/test_memory_cli.py`

**TDD Steps:**
1. Write test for `obus memory search` command
2. Run test → FAIL
3. Implement CLI commands: search, add, list, compact
4. Run test → PASS
5. Commit: `git commit -m "feat(cli): add memory management commands"`

---

## Validation

### Unit Tests
- `pytest tests/memory/ -v` (all pass)
- Coverage: 90%+ for memory modules

### Integration Tests
- Memory injected before LLM call
- Async writes don't block response path
- Token budget enforced

### Performance Targets
- Retrieval latency: <50ms (10k memories)
- Memory context: ≤600 tokens
- Token reduction: 40-60% on long conversations

### Manual Verification
```bash
# Seed memory
obus memory add --scope project --type semantic "Obus prioritizes low token usage"

# Test retrieval
obus memory search "token usage"

# Start conversation and verify memory context
```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Memory extraction LLM calls add latency | Async queue, non-blocking |
| Over-retrieval increases tokens | Strict 600 token budget, relevance threshold |
| Stale/contradictory memories | Timestamps, confidence scores, conflict detection |
| Local embeddings slower | Local-first default, API fallback option |
| SQLite concurrency limits | WAL mode, connection pooling |

---

## Open Questions

1. Should Obus support remote memory backends (Postgres + pgvector)?
2. How to handle memory schema migrations?
3. Should memory packs be gitignored or version-controlled?
4. What's the optimal starting token budget (start with 600)?

---

## Success Criteria

1. **Token Reduction:** 40-60% on conversations >10 turns
2. **Response Time:** 15-30% faster actual user-perceived latency
3. **Memory Accuracy:** >90% relevant memories in top-5 retrieval
4. **Zero Blocking:** Memory ops never increase LLM latency
5. **Transparent:** Markdown files editable by users, clear CLI

---

## Next Steps

1. Confirm tech stack (Python, existing ORM/db usage)
2. Verify actual file paths for agent loop (`backend/deck_router.py`, `obus_hermes_bridge.py`)
3. Set up `src/memory/` and `tests/memory/` directories
4. Begin Phase 1, Task 1.1 with TDD cycle