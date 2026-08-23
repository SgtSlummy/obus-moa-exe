# Obus Memory Integration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a layered AI memory system to Obus that improves response quality, reduces repeated context/token usage, and decreases perceived response latency through selective retrieval, summarization, caching, and async memory writes.

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
- "Obus prioritizes low token usage and faster response time."
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

```
src/
  memory/
    __init__.py
    schema.py         # MemoryItem, MemoryType, MemoryScope
    store.py          # SQLite store with FTS5
    retriever.py      # Token-budgeted retrieval
    writer.py         # Async write pipeline
    summarizer.py     # Session compaction
    packer.py         # Token budget utils
    extractor.py      # Automatic memory extraction
    embeddings.py     # Future: vector search
    packs.py          # File-backed memory
    router.py         # Main memory API

tests/
  memory/
    test_schema.py
    test_store.py
    test_search.py
    test_retriever.py
    test_writer.py
    test_summarizer.py
    test_extraction.py
```

---

## Memory Data Schema

Use equivalent types for Obus language/runtime.

```python
class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    RELATIONAL = "relational"

class MemoryScope(Enum):
    USER = "user"
    PROJECT = "project"
    SESSION = "session"
    GLOBAL = "global"

@dataclass
class MemoryItem:
    id: str
    content: str
    memory_type: MemoryType
    scope: MemoryScope
    importance: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = None
    confidence: float = 1.0
    provenance: str = "manual"
```

SQLite tables:

```sql
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    embedding TEXT,
    confidence REAL DEFAULT 1.0,
    provenance TEXT DEFAULT 'manual'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(id UNINDEXED, content, type UNINDEXED, scope UNINDEXED);
```

---

## Retrieval Pipeline

1. Receive user message.
2. Build a compact retrieval query from:
   - User message.
   - Active task context.
   - Project/session identifiers.
   - Working memory.
3. Query memory stores:
   - SQLite FTS/BM25.
   - File-backed project memory.
   - Hot cache if enabled.
4. Merge and deduplicate candidates.
5. Rerank by:
   - Relevance score.
   - Recency.
   - Importance.
   - Scope priority.
   - Confidence.
6. Compress selected memories into prompt-ready format.
7. Enforce token budget.
8. Inject into prompt as `## Relevant Memory` block before model call.

---

## Write Pipeline

Memory writes should happen asynchronously after the response.

1. Capture completed conversation turn.
2. Propose memory candidates via rule-based extraction.
3. Classify candidates:
   - Preference, stable fact, project decision, reusable procedure, important task outcome.
4. Reject:
   - Secrets, temporary instructions, low-confidence claims, duplicates.
5. Score importance and check for similar memories.
6. Merge or store as new memory.
7. Schedule background write queue.

---

## Token and Latency Strategy

### Token Reduction

- Do not replay full historical conversation unless explicitly needed.
- Keep memory prompt block under configurable limit (default: 600 tokens).
- Hard maximum: 1,200 tokens unless explicitly requested.
- Use rolling summaries for old turns.
- Use procedural memory instead of repeating instructions.

### Response-Time Improvements

- Enable local FTS retrieval (sub-50ms for 10k memories).
- Start retrieval as soon as user message arrives (parallel with intent classification).
- Run extraction/writes after response generation.
- Cache active user/project memories in memory.
- Defer embedding generation to background jobs.

---

## Implementation Phases & Tasks

### Phase 1: Memory Layer Foundation (Week 1-2)

**Objective:** Establish persistent storage, schemas, and basic CRUD operations.

#### Task 1: Discover Obus Project Structure

**Objective:** Identify actual language, package manager, source directories, test framework, and existing model request lifecycle files.

**Files to inspect:**
- `pyproject.toml` or `package.json`
- `src/`, `lib/`, `backend/` directory structure
- Test directory structure
- Existing agent/orchestration files

**Deliverable:**
- Confirm Python (Pytest) or TypeScript (Jest/Mocha/Vitest)
- Identify actual source root path
- Identify actual agent loop file that calls the LLM
- Map template paths to actual paths

#### Task 2: Add MemoryItem Schema

**Objective:** Define dataclasses/enums for memory items with 5-layer model.

**Files:**
- Create: `src/memory/schema.py`
- Create: `tests/memory/test_schema.py`

**TDD Cycle:**
1. Write test for MemoryItem creation
2. Run test → FAIL
3. Implement schema
4. Run test → PASS
5. Commit

#### Task 3: Initialize SQLite Memory Database

**Objective:** Add persistent storage with FTS5 for keyword search.

**Files:**
- Create: `src/memory/store.py`
- Create: `tests/memory/test_store.py`

**TDD Cycle:**
1. Write test for store CRUD
2. Run test → FAIL
3. Implement add/get/update/delete
4. Run test → PASS
5. Commit

#### Task 4: Add Basic Search and Scope Filtering

**Objective:** Enable keyword search with scope filtering.

**Files:**
- Modify: `src/memory/store.py`
- Create: `tests/memory/test_search.py`

**TDD Cycle:**
1. Write test for FTS search
2. Run test → FAIL
3. Implement search() method
4. Run test → PASS
5. Commit

### Phase 2: Session Summaries (Week 3)

**Objective:** Implement rolling session summaries to compact conversations.

#### Task 5: Create Session Summarizer

**Files:**
- Create: `src/memory/summarizer.py`
- Create: `tests/memory/test_summarizer.py`

**TDD Cycle:** Learn to summarize old turns, keep recent turns intact, store summaries as episodic memories.

#### Task 6: Integrate Summarizer with Agent Loop

**Files:**
- Modify: agent loop file (location to be discovered)

Add summary injection before LLM call when threshold exceeded.

### Phase 3: Token Budgeting (Week 4)

**Objective:** Prevent memory context from inflating prompts.

#### Task 7: Add Token Budget Utility

**Files:**
- Create: `src/memory/packer.py`
- Create: `tests/memory/test_packer.py`

**TDD Cycle:**
Implement token estimation and packing under budget constraints.

#### Task 8: Add Memory Retriever

**Files:**
- Create: `src/memory/retriever.py`
- Create: `tests/memory/test_retriever.py`

**TDD Cycle:** Implement relevance ranking, token budget enforcement, context formatting.

### Phase 4: File-Backed Memory Packs (Week 5)

**Objective:** Add Claude Mythos-inspired editable markdown files.

#### Task 9: Create Memory Pack Templates

**Files:**
- Create: `.obus/memory/user.md`
- Create: `.obus/memory/project.md`
- Create: `.obus/memory/procedures.md`
- Create: `.obus/memory/decisions.md`

#### Task 10: Implement Pack File Loader

**Files:**
- Create: `src/memory/packs.py`
- Create: `tests/memory/test_packs.py`

### Phase 5: Async Memory Writes (Week 6-7)

**Objective:** Extract and store memories automatically without blocking response.

#### Task 11: Add Memory Extractor

**Files:**
- Create: `src/memory/extractor.py`
- Create: `tests/memory/test_extractor.py`

**TDD Cycle:** Rule-based classification of durable facts vs transient instructions.

#### Task 12: Add Write Queue

**Files:**
- Create: `src/memory/queue.py`
- Create: `tests/memory/test_queue.py`

**TDD Cycle:** Implement non-blocking queue that processes after responses.

#### Task 13: Integrate Writes into Agent Loop

**Files:**
- Modify: agent loop file

Add post-response queue trigger for memory extraction.

### Phase 6: Vector/Retrieval Enhancement (Week 8-9, Optional)

**Objective:** Add semantic search via embeddings for improved recall.

#### Task 14: Add Embedding Provider

**Files:**
- Create: `src/memory/embeddings.py`
- Create: `tests/memory/test_embeddings.py`

#### Task 15: Hybrid Search

**Files:**
- Modify: `src/memory/retriever.py`

Combine BM25 and vector similarity with token budget.

### Phase 7: CLI Management (Week 10)

**Objective:** Provide user commands for memory inspection and management.

#### Task 16: Add Memory CLI Commands

**Files:**
- Modify: CLI entry point (location to be discovered)
- Create: `tests/test_memory_cli.py`

Commands:
- `obus memory add --scope project "fact content"`
- `obus memory search "query"`
- `obus memory list --scope project`
- `obus memory delete <id>`

---

## Testing & Validation Strategy

### Unit Tests
Each module has corresponding test file with full TDD cycle.

### Integration Tests
- End-to-end memory retrieval before LLM call
- Async write queue does not block response
- Token budget enforced in all scenarios

### Performance Targets
- Retrieval p95 < 50ms for 10k memories (local FTS)
- Memory prompt block default ≤ 600 tokens
- Response time: 15-30% faster on long conversations
- Token reduction: 40-60% on sessions >10 turns

---

## Risks, Tradeoffs, and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Memory extraction adds latency | High | Always async, non-blocking queue |
| Over-retrieval increases tokens | High | Strict budgets, relevance thresholds |
| Stale/contradictory memories | Medium | Timestamps, confidence scores, provenance |
| Local embeddings slower than API | Medium | Optional hybrid mode |
| SQLite concurrency limits | Low | WAL mode, connection pooling |
| Secrets leak to memory | High | Content filters, write rejection, user deletion tools |

---

## Success Criteria

1. ✅ Token reduction: 40-60% on conversations >10 turns
2. ✅ Response time: 15-30% faster user-perceived latency
3. ✅ Memory accuracy: >90% relevant memories in top-5 retrieval
4. ✅ Zero blocking: No memory op increases LLM latency
5. ✅ Developer experience: Editable markdown packs, clear CLI

---

## Immediate Next Steps

1. Run Task 1: Discover Obus project structure and actual file paths
2. Set up `src/memory/` and `tests/memory/` directories
3. Begin Phase 1 implementation

---

**Plan complete and saved to:** `.hermes/plans/2026-08-23_1435-obus-memory-integration.md`