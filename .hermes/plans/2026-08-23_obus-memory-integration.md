# Obus Memory System Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate a layered AI memory system into Obus to improve response quality, reduce repeated context/token usage, and decrease perceived response latency through selective retrieval, summarization, caching, and async memory writes.

**Architecture:** Implement memory as a modular subsystem with working, episodic, semantic, procedural, and optional graph memory layers. Retrieval happens before model calls with strict token budgets; memory extraction and consolidation happen asynchronously after responses so the critical path remains fast. Start with local-first SQLite/FTS/file-backed memory, then add embeddings and graph/entity memory only after the baseline works.

**Tech Stack:** Obus existing application stack, SQLite with FTS5, optional vector store such as sqlite-vss/Chroma/LanceDB, markdown/YAML file-backed memory packs, background job queue/worker if Obus already has one, and test framework already used by the repo.

---

## Current Context / Assumptions

- The user wants the ideas from:
  - `https://aiagentmemory.org/articles/how-to-give-llm-memory/`
  - `https://github.com/anshug/claude-mythos`
  - `https://aiagentmemory.org/articles/ai-memory-system-github/`
  incorporated into a formal plan for Obus.
- Obus should gain:
  - Better long-running context continuity.
  - Lower prompt token usage.
  - Faster response time by avoiding full conversation replay.
  - Durable project/user memory.
  - Transparent, inspectable memory files.
- Exact Obus file paths are not yet confirmed in this conversation, so Task 1 performs repository discovery and maps the proposed paths to the real structure.
- Candidate design inspirations to validate during implementation:
  - Claude Mythos / Claude memory utilities: file-backed memory and durable project lore.
  - Mem0: automatic memory extraction, scoring, deduplication.
  - Zep: session summaries and conversational memory.
  - Letta / MemGPT: separation of working and archival memory.
  - LangMem / LangGraph-style patterns: memory as explicit graph/state primitives.
  - Graphiti / Cognee-style systems: optional entity and relationship memory.

---

## Proposed Memory Model

### 1. Working Memory

Short-lived state for the current request/task.

Examples:
- Current user goal.
- Active constraints.
- Tool state.
- Open questions.
- Current plan step.

Storage:
- In process memory.
- Optional persisted checkpoint per session.

Prompt usage:
- Always included, but compact.
- Target budget: 100–300 tokens.

### 2. Episodic Memory

Summaries of prior conversations, tasks, tool results, decisions, and outcomes.

Examples:
- "User asked to research AI memory systems for Obus."
- "Obus memory integration plan was created on YYYY-MM-DD."
- "Previous implementation attempt failed because vector retrieval was unbounded."

Storage:
- SQLite table.
- FTS index.
- Optional embedding column.

Prompt usage:
- Retrieved only when relevant.
- Target budget: 200–600 tokens.

### 3. Semantic Memory

Stable facts about the user, projects, tools, and preferences.

Examples:
- "User prefers concrete implementation plans."
- "Obus prioritizes low token usage and fast response time."
- "The memory system should be local-first unless configured otherwise."

Storage:
- SQLite table.
- FTS index.
- Embeddings once vector search is added.
- Confidence and provenance metadata.

Prompt usage:
- Retrieved by relevance and scope.
- Target budget: 200–500 tokens.

### 4. Procedural Memory

Reusable workflows and "how to do things."

Examples:
- "How to run computer-use doctor."
- "How to create a formal Hermes plan."
- "How to compact old conversation history."

Storage:
- Human-editable markdown/YAML files under a project memory directory.
- Optional SQLite index for search.

Prompt usage:
- Retrieved when the task matches a known workflow.
- Target budget: 200–800 tokens.

### 5. Optional Graph / Relational Memory

Entity and relationship tracking for larger projects.

Examples:
- User -> works_on -> Obus.
- Obus -> uses -> memory subsystem.
- Memory subsystem -> contains -> episodic memory.

Storage:
- SQLite tables for entities and edges initially.
- Later optional Graphiti-style temporal graph.

Prompt usage:
- Used for disambiguation and targeted recall.
- Not part of Phase 1.

---

## Target User-Facing Behavior

Before:
- Obus repeatedly includes large prior context.
- Long conversations become expensive.
- Responses slow down as transcripts grow.
- User preferences must be restated.

After:
- Obus retrieves only relevant memories.
- Old turns are summarized and compacted.
- Stable preferences persist across sessions.
- The prompt stays small and targeted.
- Memory writes do not block response generation.

---

## Proposed Directory Layout

Adjust paths after Task 1 repository discovery.

```text
.obus/
  memory/
    user.md
    project.md
    procedures.md
    decisions.md
    summaries.md

src/
  memory/
    __init__.py
    schema.py
    store.py
    router.py
    retriever.py
    writer.py
    summarizer.py
    token_budget.py
    config.py

tests/
  memory/
    test_schema.py
    test_store.py
    test_router.py
    test_retriever.py
    test_writer.py
    test_summarizer.py
    test_token_budget.py
```

---

## Memory Data Schema

Use equivalent types for Obus language/runtime.

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime

class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    DECISION = "decision"
    SUMMARY = "summary"

class MemoryScope(str, Enum):
    GLOBAL = "global"
    USER = "user"
    PROJECT = "project"
    SESSION = "session"

@dataclass
class MemoryItem:
    id: str
    type: MemoryType
    content: str
    summary: str = ""
    source: str = "manual"
    projectId: Optional[str] = None
    sessionId: Optional[str] = None
    userId: Optional[str] = None
    confidence: float = 0.5
    importance: float = 0.5
    createdAt: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updatedAt: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expiresAt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

SQLite tables:

```sql
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT NOT NULL,
    project_id TEXT,
    session_id TEXT,
    user_id TEXT,
    confidence REAL NOT NULL DEFAULT 0.5,
    importance REAL NOT NULL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(id UNINDEXED, content, summary, type UNINDEXED, scope UNINDEXED);
```

---

## Retrieval Pipeline

1. Receive user message.
2. Build a compact retrieval query from:
   - User message.
   - Active task.
   - Project/session identifiers.
   - Current working memory.
3. Query memory stores:
   - Hot cache.
   - SQLite FTS/BM25.
   - Vector index if enabled.
   - File-backed project memory.
4. Merge and deduplicate candidates.
5. Rerank by:
   - Relevance.
   - Recency.
   - Importance.
   - Scope priority.
   - Confidence.
6. Compress selected memories.
7. Enforce token budget.
8. Inject into prompt as a concise `Relevant Memory` block.

---

## Write Pipeline

Memory writes should usually happen after the response and off the critical path.

1. Capture completed conversation turn.
2. Propose memory candidates.
3. Classify candidates:
   - Preference.
   - Durable fact.
   - Project decision.
   - Reusable procedure.
   - Task summary.
4. Reject:
   - Secrets.
   - One-off instructions.
   - Low-confidence claims.
   - Duplicate memories.
   - Raw tool noise.
5. Score importance and confidence.
6. Merge with existing memories if similar.
7. Commit to SQLite and/or file-backed memory.
8. Schedule summarization/compaction if needed.

---

## Token and Latency Strategy

### Token Reduction

- Do not replay full historical conversation unless explicitly needed.
- Keep memory prompt block under a configurable limit.
- Default memory token budget: 600 tokens.
- Hard maximum: 1,200 tokens unless user explicitly asks for broader context.
- Use rolling summaries for old turns.
- Use procedural memory instead of repeatedly injecting long instructions.

### Response-Time Improvements

- Keep retrieval local and fast.
- Use FTS first; vector search can be optional and cached.
- Run memory extraction after response generation.
- Cache active user/project memories.
- Use embedding generation in background jobs, not the request path.

---

## Implementation Tasks

### Phase 1: Memory Layer Foundation (1-2 weeks)

**Objective:** Establish persistent storage, schemas, and basic CRUD operations.

#### Task 1: Discover Obus Project Structure

**Objective:** Identify the real language, package manager, source directories, test framework, and existing model/request lifecycle files.

**Discovery File:** `src/memory/discovery.json` (optional - for mapping)

**TDD Cycle:**
1. Explore `package.json`, `pyproject.toml`, `Cargo.toml`, or `go.mod` to identify language.
2. Locate test configuration and run command.
3. Identify where model calls happen (agent loop, orchestrator, etc.).
4. Record discovered paths in a discovery log (file or terminal output).

#### Task 2: Add Memory Configuration

**Objective:** Add configuration for memory behavior (token budget, storage path, thresholds, file pack location).

**Files:**
- Create: `src/memory/config.py`
- Modify: existing config file
- Create: `tests/memory/test_config.py`

#### Task 3: Define MemoryItem Schema

**Objective:** Define dataclasses for memory items with 5-layer model and SQLite-compatible types.

**Files:**
- Create: `src/memory/schema.py`
- Create: `tests/memory/test_schema.py`

#### Task 4: Initialize SQLite Memory Database

**Objective:** Add persistent storage with FTS5 for full-text keyword search.

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/memory/test_store.py`

#### Task 5: Add Basic Search and Scope Filtering

**Objective:** Enable keyword search with scope filtering (global/user/project/session).

**Files:**
- Modify: `src/memory/store.py`
- Create: `tests/memory/test_search.py`

### Phase 2: Session Summaries (Week 3)

**Objective:** Implement rolling session summaries to compact old conversations.

#### Task 6: Create Session Summarizer

**Files:**
- Create: `src/memory/summarizer.py`
- Create: `tests/memory/test_summarizer.py`

#### Task 7: Integrate Summarizer with Agent Loop

**Files:**
- Modify: agent loop/orchestration file

### Phase 3: Token Budgeting (Week 4)

**Objective:** Prevent memory context from inflating prompts.

#### Task 8: Add Token Budget Utility

**Files:**
- Create: `src/memory/packer.py`
- Create: `tests/memory/test_packer.py`

#### Task 9: Add Memory Retriever

**Files:**
- Create: `src/memory/retriever.py`
- Create: `tests/memory/test_retriever.py`

### Phase 4: File-Backed Memory Packs (Week 5)

**Objective:** Add Claude Mythos-inspired editable memory files.

#### Task 10: Create Memory Pack Templates

**Files:**
- Create: `src/memory/packs.py`
- Create: `.obus/memory/user.md`
- Create: `.obus/memory/project.md`
- Create: `.obus/memory/procedures.md`
- Create: `.obus/memory/decisions.md`

### Phase 5: Async Memory Writes (Week 6-7)

**Objective:** Improve response time by extracting and storing memories after the user sees the response.

#### Task 11: Add Memory Extractor

**Files:**
- Create: `src/memory/extractor.py`
- Create: `tests/memory/test_extractor.py`

#### Task 12: Add Write Queue

**Files:**
- Create: `src/memory/queue.py`
- Create: `tests/memory/test_queue.py`

#### Task 13: Integrate Writes into Agent Loop

**Files:**
- Modify: agent loop file

### Phase 6: Automatic Memory Integration (Week 8)

**Objective:** Connect retrieval and writes to actual model calls.

#### Task 14: Add Memory Router

**Files:**
- Create: `src/memory/router.py`
- Create: `tests/memory/test_router.py`

#### Task 15: Integrate Retrieval Before Model Calls

**Files:**
- Modify: model request/orchestration file

### Phase 7: Vector Search (Week 9-10, Optional)

**Objective:** Add semantic search via embeddings while keeping Phase 1 functionality local and fast.

#### Task 16: Add Embedding Provider

**Files:**
- Create: `src/memory/embeddings.py`
- Create: `tests/memory/test_embeddings.py`

#### Task 17: Hybrid Search

**Files:**
- Modify: `src/memory/retriever.py`
- Modify: `src/memory/store.py`

### Phase 8: Safety & Privacy (Week 11)

**Objective:** Prevent memory poisoning, accidental secret storage, and stale memory.

**Files:**
- Create: `src/memory/safety.py`
- Create: `tests/memory/test_safety.py`

### Phase 9: CLI & Management (Week 12)

**Objective:** Allow users/developers to inspect, add, search, and delete memory.

**Files:**
- Modify: CLI entry point
- Create: `tests/test_memory_cli.py`

Commands:
- `obus memory add --scope project --type semantic "fact content"`
- `obus memory search "query"`
- `obus memory list --scope project`
- `obus memory delete <id>`

### Phase 10: Documentation & Benchmarks (Ongoing)

**Files:**
- Create: `docs/memory.md`
- Create: `benchmarks/memory_retrieval.py`
- Create: `benchmarks/token_compaction.py`

---

## Testing Strategy

### Unit Tests (TDD per task)
- Schema, store, search, config, packer, extractor, retriever, writer, router, embeddings, safety

### Integration Tests
1. Memory injected before LLM call
2. Token budgets enforced
3. Session summaries compact turns
4. Async writes don't block response

### Performance Targets
- Retrieval p95 < 50ms (local FTS, 10k memories)
- Memory block ≤ 600 tokens default
- 40-60% token reduction on long sessions
- 15-30% faster response time

### Validation Commands
```bash
pytest tests/memory/ -v --cov=src/memory
obus memory add --scope project --type semantic "Obus prioritizes low token usage"
obus memory search "token usage"
```

---

## Success Criteria

1. **Token Reduction:** 40-60% on conversations >10 turns
2. **Response Time:** 15-30% faster user-perceived latency
3. **Memory Accuracy:** >90% relevant memories retrieved in top-5
4. **Zero Blocking:** No memory op increases LLM latency
5. **Developer Experience:** Editable packs, clear CLI

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Memory extraction adds latency | High | Always async, non-blocking queue |
| Over-retrieval bloats prompts | High | Strict token budgets, relevance thresholds |
| Stale/contradictory memories | High | Timestamps, confidence, conflict detection |
| Secrets leak to memory | Critical | Secret detection, default rejection |
| Too much architecture too soon | Medium | Phase implementation: FTS/file-backed first |

---

## Next Immediate Steps

1. Explore Obus codebase structure (`src/`, `tests/`, agent loop files)
2. Confirm tech stack (Python vs TypeScript, ORMs, test frameworks)
3. Set up `src/memory/` and `tests/memory/` directories
4. Begin Task 1: Discover project structure