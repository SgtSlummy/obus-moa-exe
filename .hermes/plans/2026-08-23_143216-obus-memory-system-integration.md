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

Based on my earlier research, these are **research-informed patterns / candidate projects to validate**:

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
- Storage: In-process memory
- Target budget: 100–300 tokens
- Always included but compact

### 2. Episodic Memory (Conversation Summaries)
- Prior conversation summaries, decisions, outcomes
- Storage: SQLite table with FTS index
- Target budget: 200–600 tokens
- Retrieved only when relevant

### 3. Semantic Memory (Stable Facts)
- User preferences, project facts, architectural decisions
- Storage: SQLite table with optional embeddings
- Target budget: 200–500 tokens
- Retrieved by relevance and scope

### 4. Procedural Memory (Reusable Workflows)
- Human-editable markdown files with step-by-step procedures
- Example: "How to run computer-use doctor"
- Loaded based on task type matching

### 5. Graph/Relational Memory (Optional)
- Entity relationships (User → Project → Tool → Issue)
- Phase 6 enhancement

---

## Proposed Approach

1. **Add Memory Layer Foundation** — SQLite store with FTS5, basic schemas, manual APIs
2. **Session Summaries** — Rolling compaction of conversation history
3. **Vector Retrieval** — Hybrid BM25 + vector search with token budgets
4. **Automatic Memory Writes** — Async post-response extraction pipeline
5. **File-Backed Memory Packs** — Claude Mythos-style markdown files
6. **Graph Memory (Optional)** — Entity relationships for advanced use cases

**Key Design Principles:**
- Async by default: no memory operation blocks the LLM response path
- Token-budgeted: strict limits on memory context size
- Local-first: SQLite + optional vector extension, no mandatory cloud services
- Transparent: markdown files for human review and version control

---

## Step-by-Step Implementation Plan

### Phase 1: Memory Layer Foundation (Week 1-2)

**Objective:** Establish persistent storage, schemas, and basic CRUD operations for memory items.

#### Task 1.1: Define MemoryItem Schema

**Files:**
- Create: `src/memory/schema.py` (Python) or `src/memory/schema.ts` (TypeScript)
- Create: `tests/memory/test_schema.py`

**TDD Cycle:**
1. Write failing test for MemoryItem creation with all fields
2. Run test → FAIL
3. Implement MemoryItem, MemoryType, MemoryScope enums, dataclasses
4. Run test → PASS
5. Commit

#### Task 1.2: Initialize SQLite Memory Database

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/memory/test_store.py`

TDD cycle for MemoryStore with CRUD operations and FTS5 index.

#### Task 1.3: Add Basic Search and Scope Filtering

**Files:**
- Modify: `src/memory/store.py`
- Create: `tests/memory/test_search.py`

TDD cycle for keyword search with scope filtering.

### Phase 2: Session Summaries (Week 3)

**Objective:** Implement rolling session summaries to compact old conversations.

#### Task 2.1: Create Summary Service

**Files:**
- Create: `src/memory/summarizer.py`
- Create: `tests/memory/test_summarizer.py`

Implement SessionSummarizer with sliding window and compaction.

#### Task 2.2: Integrate with Agent Loop

**Files:**
- Modify: `src/agent/loop.py` (or detect actual agent orchestration file)

Add summary injection before LLM call when threshold exceeded.

### Phase 3: Vector Retrieval (Week 4-5)

**Objective:** Add semantic search via embeddings while keeping local-first option.

#### Task 3.1: Add Embedding Provider

**Files:**
- Create: `src/memory/embeddings.py`
- Modify: `src/memory/store.py`

Support local embeddings (sentence-transformers) or API, add upsert_with_embedding method.

#### Task 3.2: Hybrid Search

**Files:**
- Modify: `src/memory/store.py`

Combine BM25 and vector similarity scores.

#### Task 3.3: Token-Budgeted Context Packing

**Files:**
- Create: `src/memory/packer.py`

Implement MemoryPacker class to pack memories under budget.

### Phase 4: Automatic Memory Writes (Week 6-7)

**Objective:** Extract and store memories automatically after each conversation turn.

**Files:**
- Create: `src/memory/extractor.py`
- Create: `src/memory/queue.py`
- Modify: `src/agent/loop.py`

**Write Criteria:**
- Write if: durable preference, stable fact, explicit decision, reusable procedure, important task outcome
- Never write: secrets/PII, temporary instructions, low-confidence claims, duplicates, raw tool noise

### Phase 5: File-Backed Memory Packs (Week 8)

**Objective:** Add Claude Mythos-inspired transparent markdown memory packs.

**Files:**
- Create: `src/memory/packs.py`
- Create: `.obus/memory/user.md`
- Create: `.obus/memory/project.md`
- Create: `.obus/memory/procedures.md`
- Create: `.obus/memory/decisions.md`

### Phase 6: Graph/Temporal Memory (Optional)

**Files:**
- Create: `src/memory/graph.py`

Track entity relationships with temporal validity.

---

## Integration Points with Existing Obus Code

**Likely files to modify:**
- Agent loop/orchestration file — inject memory retrieval before LLM call
- Configuration files — add memory settings
- CLI entry point — add `obus memory` commands
- Build/deployment scripts — include memory assets

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
**Integration Tests:** Memory injection, async writes, token budget enforcement
**Validation Commands:**
- `pytest tests/memory/ -v`
- `obus memory search "token usage"`
- `obus memory add --scope project "Obus prioritizes low token usage"`

---

## Risks, Tradeoffs, and Open Questions

| Risk | Mitigation |
|---|---|
| Over-retrieval increases tokens | Strict token budgets, relevance thresholds |
| Memory extraction blocks response | Async queue, background workers |
| Stale/contradictory memories | Timestamps, confidence scores, provenance |
| Secrets leak to memory | Secret filters, default rejection |

---

## Success Criteria

1. 40-60% token reduction on conversations >10 turns
2. 15-30% faster response time
3. >90% relevant memories retrieved
4. Zero blocking memory operations
5. Editable markdown packs for transparency

---

## Immediate Next Steps

1. Scan `src/` directory structure to confirm file layout
2. Identify agent/orchestration entry point
3. Set up `src/memory/` and `tests/memory/` directories
4. Begin Phase 1 Task 1.1

**Plan complete and saved.** Ready to execute using subagent-driven-development when confirmed.