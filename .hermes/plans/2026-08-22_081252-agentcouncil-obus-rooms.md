# AgentCouncil Rooms and Forum Integration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Integrate the protocol ideas from Sentry01/AgentCouncil into OBus so each isolated Tarot hand/spread becomes a room with its own multi-agent council, while one Chymeria representative per room communicates the room's decisions through a shared forum.

**Architecture:** OBus will keep its existing Tarot-card persona, Solomon's Key, MemoryHub, and Tarot Router layers. A new room runtime will execute an AgentCouncil-style three-phase protocol inside each room: independent card drafts, cross-card improvement or adversarial attack, and a room-level Chymeria synthesis. Rooms will not exchange raw internal transcripts; they publish structured decision packets to a forum, and each room's Chymeria reads forum packets, replies, and records the room's updated position. The first implementation should use persisted JSON state plus REST polling, not a new broker or websocket dependency.

**Tech Stack:** Existing FastAPI/Pydantic backend, JSON state under `OCCULTBUS_HOME`, vanilla JavaScript UI in `backend/static/index.html`, `unittest` + FastAPI `TestClient`, existing Tarot Router/Solomon's Keys provider selection, and AgentCouncil's MIT-marked collaborative/adversarial protocol as a design reference rather than a direct Copilot CLI dependency.

---

## Research Findings and Design Decisions

- `https://github.com/Sentry01/AgentCouncil` is a markdown-only GitHub Copilot CLI skill/agent, not a Python package or service. Its reusable concept is the protocol: three distinct roles in parallel, then an improve/attack round, then an orchestrator synthesis.
- Collaborative mode is: draft independently -> each agent reads the other drafts and improves -> orchestrator synthesizes.
- Adversarial mode is: draft independently -> orchestrator triages -> non-leading agents attack -> orchestrator issues a verdict.
- The repository README states that the default council is seven calls in collaborative mode and six in adversarial mode, and that the complexity gate skips councils for trivial work. OBus should preserve this gate and make room participation configurable rather than blindly multiplying calls.
- Current OBus already has `select_cards_for_prompt`, `match_cards_to_keys`, `/api/route/plan`, `/api/route/run`, persistent `state["cards"]`, `state["keys"]`, `aggregator_key_id`, `MemoryHub`, and a local MoA/Ollama fallback. There is currently no room, spread, forum, or per-room transcript model.
- The OBus UI is a single-task dashboard. It already renders cards, keys, decks, Forge assignments, memory, and route output, so Rooms/Forum should be a new page rather than a second application.
- The existing repository has uncommitted source and generated-artifact changes. Implementation must not reset, overwrite, or clean those changes; only the files listed below should be intentionally edited.

### Terminology used by this plan

- **Hand/spread:** A user-defined ordered set of Tarot card IDs selected for one room. A hand is the room's private council membership; it is not the whole 78-card catalog.
- **Room:** An isolated execution and transcript boundary containing one hand/spread, one council mode, one local decision log, and one Chymeria representative.
- **Chymeria:** OBus's logical room representative. It is a single synthesis persona/context per room, backed by a selected ready Solomon's Key, and speaks for the room in the forum. It must never expose hidden raw card transcripts unless the user explicitly opens the room.
- **Forum:** A shared thread containing only room-to-room decision packets, questions, replies, citations, and status updates. A forum thread can include multiple rooms, but a room's private drafts remain isolated.
- **Decision packet:** Stable JSON containing the room's current position, confidence, unresolved questions, evidence references, and requested responses. This is the only default cross-room payload.

### Recommended first release scope

1. Support 2-20 rooms per OBus process.
2. Support collaborative and adversarial modes, with collaborative as the default.
3. Use bounded, sequential phases with parallel card work inside a room; do not create unbounded nested agents.
4. Use HTTP polling for forum updates. Add streaming only after the state model and tests are stable.
5. Keep provider credentials reference-only. Resolve a room's Chymeria and card assignments through the existing ready/connected Solomon's Key logic.
6. Keep one optional global aggregator for an explicit final synthesis; do not silently turn every forum into one giant council.

---

## Task 1: Add the room, forum, and decision-packet data model

**Objective:** Define serializable Pydantic models and deterministic state helpers without running any model calls.

**Files:**
- Create: `backend/room_models.py`
- Modify: `backend/main.py:202-242` (state normalization and persistence)
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Add tests covering:

```python
def test_default_state_contains_no_rooms_or_forum_threads(self):
    state = backend.load_state()
    self.assertEqual(state["rooms"], [])
    self.assertEqual(state["forum_threads"], [])


def test_room_model_requires_unique_card_ids_and_has_one_chymeria(self):
    room = backend.RoomCreate(
        name="Security hand",
        card_ids=["card-hermit", "card-devil"],
        mode="adversarial",
    )
    self.assertEqual(room.mode, "adversarial")
    self.assertEqual(len(set(room.card_ids)), 2)


def test_decision_packet_contains_only_public_forum_fields(self):
    packet = backend.DecisionPacket(
        room_id="room-a", revision=1, position="Use signed packets", confidence="high",
        unresolved_questions=["How should replay be handled?"], evidence_refs=["msg-1"],
    )
    serialized = packet.model_dump_json().lower()
    self.assertNotIn("api_key", serialized)
    self.assertNotIn("token", serialized)
    self.assertIn("position", serialized)
```

**Step 2: Run tests to verify failure**

Run from `C:/Users/Hermes/Documents/obus-moa-exe`:

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_default_state_contains_no_rooms_or_forum_threads -v
```

Expected: FAIL because room models/state defaults do not exist.

**Step 3: Implement the minimal model layer**

`backend/room_models.py` should define:

- `ROOM_MODES = {"collaborative", "adversarial"}`
- `RoomCreate(name, card_ids, mode="collaborative", chymeria_card_id=None, chymeria_key_id=None)`
- `RoomUpdate(...)` with optional fields
- `RoomMessage(author_type, author_id, kind, body, visibility="room", reply_to=None, packet=None)`
- `DecisionPacket(room_id, revision, position, confidence, rationale, evidence_refs, unresolved_questions, requested_responses, status="provisional")`
- `ForumThreadCreate(title, room_ids, prompt, mode="collaborative")`
- `ForumMessageCreate(room_id, kind, body, reply_to=None)`

Validate duplicate card IDs, non-empty names/prompts, legal modes, legal visibility (`room` or `forum`), and a bounded body length. Models must reject credential-shaped fields rather than accepting arbitrary extra data.

Add `rooms`, `forum_threads`, and `room_messages` defaults in `normalize_state`. Preserve unknown existing state keys and all existing key/card normalization behavior.

**Step 4: Run the focused tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_default_state_contains_no_rooms_or_forum_threads tests.test_runtime.RuntimeContractTests.test_room_model_requires_unique_card_ids_and_has_one_chymeria tests.test_runtime.RuntimeContractTests.test_decision_packet_contains_only_public_forum_fields -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/room_models.py backend/main.py tests/test_runtime.py
git commit -m "feat: define isolated room and forum models"
```

---

## Task 2: Implement room lifecycle and isolation endpoints

**Objective:** Allow the UI and future runners to create, inspect, update, and archive rooms while guaranteeing card/key references are valid.

**Files:**
- Modify: `backend/main.py` near the card/key endpoints, after state/model definitions
- Modify: `backend/room_models.py` if validation needs a shared helper
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Add tests for:

- `POST /api/rooms` creates a room with generated `room_id`, selected card IDs, mode, an explicit or deterministic Chymeria card, and a ready/connected Chymeria key when available.
- Invalid card IDs return `400`.
- Duplicate card IDs return `400`.
- A room cannot use a staged/disabled/unconnected key as Chymeria.
- `GET /api/rooms/{room_id}` returns metadata and counts, but not private raw messages by default.
- `PUT /api/rooms/{room_id}` changes mode/name/active state and preserves the room ID.
- `DELETE /api/rooms/{room_id}` archives the room and does not delete another room's messages.

**Step 2: Run the focused tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_create_room_uses_selected_cards_and_one_chymeria -v
```

Expected: FAIL because `/api/rooms` is not registered.

**Step 3: Implement lifecycle endpoints**

Add these endpoints:

- `POST /api/rooms`
- `GET /api/rooms`
- `GET /api/rooms/{room_id}`
- `PUT /api/rooms/{room_id}`
- `DELETE /api/rooms/{room_id}` (archive, not destructive delete)
- `GET /api/rooms/{room_id}/messages`

Use the existing `load_state()`/`save_state()` pattern. Add a helper such as `choose_room_chymeria(room, state)` that prefers an explicitly selected card/key only when valid, otherwise chooses a selected card with synthesis/analysis capability and the first eligible ready/connected aggregator-capable key. Return only public key metadata (`id`, `name`, `model`, `max_context_tokens`, `sigil`), never credential values.

A room record should contain:

```json
{
  "id": "room-security",
  "name": "Security hand",
  "card_ids": ["card-hermit", "card-devil", "card-tower"],
  "mode": "adversarial",
  "chymeria": {"card_id": "card-hermit", "key_id": "key-local-ollama"},
  "status": "idle",
  "revision": 0,
  "created_at": "...",
  "updated_at": "..."
}
```

No room runner may read another room's private messages while building a room-local prompt.

**Step 4: Run the focused tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_create_room_uses_selected_cards_and_one_chymeria tests.test_runtime.RuntimeContractTests.test_room_private_messages_are_isolated -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/main.py backend/room_models.py tests/test_runtime.py
git commit -m "feat: add isolated room lifecycle APIs"
```

---

## Task 3: Add the AgentCouncil phase planner for one room

**Objective:** Translate AgentCouncil's collaborative/adversarial protocol into deterministic OBus phase plans without making provider calls yet.

**Files:**
- Create: `backend/room_council.py`
- Modify: `backend/main.py` to expose the planner
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Test that:

```python
def test_collaborative_room_plan_has_draft_improve_synthesize(self):
    plan = backend.build_room_council_plan(room, prompt="Design a secure sync protocol")
    self.assertEqual([phase["name"] for phase in plan["phases"]], ["draft", "improve", "synthesize"])
    self.assertEqual(plan["mode"], "collaborative")


def test_adversarial_room_plan_has_draft_triage_attack_verdict(self):
    plan = backend.build_room_council_plan(room, prompt="Stress-test room isolation")
    self.assertEqual([phase["name"] for phase in plan["phases"]], ["draft", "triage", "attack", "verdict"])


def test_simple_prompt_short_circuits_room_council(self):
    plan = backend.build_room_council_plan(room, prompt="What is 2 + 2?")
    self.assertTrue(plan["short_circuit"])
```

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_collaborative_room_plan_has_draft_improve_synthesize -v
```

Expected: FAIL because the planner does not exist.

**Step 3: Implement the planner**

`backend/room_council.py` should provide:

- `detect_room_mode(prompt, configured_mode)` with explicit room configuration taking precedence and adversarial trigger words (`debate`, `stress-test`, `attack`, `versus`) recognized only when mode is auto.
- `is_council_worthy(prompt)` for the complexity gate.
- `build_room_council_plan(room, prompt)` returning room ID, mode, selected card seats, Chymeria seat, max parallelism, and phases.
- `build_card_prompt(room, card, phase, prompt, peer_packets)` that includes only room-local context.
- `build_chymeria_prompt(room, prompt, decision_packets, forum_packets=[])` that tells the representative to speak for the whole room and return a schema-valid decision packet.

The planner must use the room's selected cards, not the global top-five selection, and must use the existing provider-assignment result for card-to-Key resolution. The plan should expose `parallel_groups` for the executor, but not invoke `asyncio.gather` itself.

Keep the model-family diversity rule compatible with Tarot Router: use ready cards/keys only, avoid staged keys, and never create accounts or rotate credentials. If fewer than three eligible card/key seats exist, lower the council size and report the reason in the plan.

**Step 4: Run tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_collaborative_room_plan_has_draft_improve_synthesize tests.test_runtime.RuntimeContractTests.test_adversarial_room_plan_has_draft_triage_attack_verdict tests.test_runtime.RuntimeContractTests.test_simple_prompt_short_circuits_room_council -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/room_council.py backend/main.py tests/test_runtime.py
git commit -m "feat: plan AgentCouncil phases per room"
```

---

## Task 4: Implement room-local execution and Chymeria synthesis

**Objective:** Execute a room council with isolated context, persist phase messages, and publish one room decision packet.

**Files:**
- Create: `backend/room_runner.py`
- Modify: `backend/main.py` to add execution endpoints
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Mock the model boundary and test:

- Draft calls receive only their room's prompt and card persona.
- Improve/attack calls receive peer drafts from the same room and no other room's messages.
- Chymeria receives all approved room outputs and returns exactly one decision packet.
- A failed card call is recorded as an error and does not leak its provider error into the forum.
- Room revision increments atomically after a successful synthesis.

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_room_run_persists_one_chymeria_decision_packet -v
```

Expected: FAIL because `/api/rooms/{room_id}/run` and the runner do not exist.

**Step 3: Implement the runner**

`backend/room_runner.py` should define a narrow model adapter interface:

```python
class RoomModelAdapter(Protocol):
    async def complete(self, *, key: dict, model: str, system: str, prompt: str) -> str: ...
```

Implement an OBus adapter that reuses the existing local Ollama/MoA boundary instead of embedding provider-specific credentials. Keep the adapter injectable for tests.

Implement:

- `run_room(room_id, prompt, state, adapter)`
- collaborative phases: draft -> improve -> Chymeria synthesis
- adversarial phases: draft -> local triage -> attack by non-leaders -> Chymeria verdict
- structured JSON extraction/validation for `DecisionPacket`
- message persistence with `room_id`, `phase`, `author_id`, `visibility="room"`, timestamps, and redacted error status
- deterministic prompt-size limits based on the Chymeria Key's configured context window
- complexity-gate direct answer path with no multi-agent calls

The public result should return room status, phase summaries, the Chymeria identity, and the decision packet. Do not return raw prompts, tokens, or private credentials.

Add:

- `POST /api/rooms/{room_id}/run`
- `GET /api/rooms/{room_id}/runs/{run_id}`

Use the existing background-job pattern used by Codex and Forge if execution is long-running. Do not block the FastAPI event loop.

**Step 4: Run tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_room_run_persists_one_chymeria_decision_packet tests.test_runtime.RuntimeContractTests.test_room_run_does_not_read_other_room_messages -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/room_runner.py backend/main.py tests/test_runtime.py
 git commit -m "feat: execute isolated room councils"
```

---

## Task 5: Add forum threads and room-to-room Chymeria communication

**Objective:** Let multiple room representatives exchange decision packets in a forum while preserving room isolation.

**Files:**
- Create: `backend/forum_runtime.py`
- Modify: `backend/main.py`
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Cover:

- Creating a forum thread with two or more room IDs.
- Rejecting unknown, archived, or duplicate room IDs.
- Posting a room's decision packet creates a forum message authored by that room's Chymeria, not by individual cards.
- A room can read forum packets from other participating rooms but cannot read their private transcripts.
- Replying to a forum message records `reply_to` and the responding room ID.
- Replaying the same packet revision is idempotent.
- Forum messages contain no `api_key`, `token`, raw prompt, or hidden room draft.

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_forum_allows_room_chymeria_replies_without_private_transcript_leak -v
```

Expected: FAIL because forum endpoints do not exist.

**Step 3: Implement the forum runtime**

Add endpoints:

- `POST /api/forum/threads`
- `GET /api/forum/threads`
- `GET /api/forum/threads/{thread_id}`
- `POST /api/forum/threads/{thread_id}/messages`
- `POST /api/forum/threads/{thread_id}/round`

`/round` should:

1. Snapshot each participating room's latest approved decision packet.
2. Deliver only that public packet set to each room's Chymeria.
3. Run participating rooms in parallel where provider capacity allows.
4. Persist one response packet per room with a forum visibility marker.
5. Advance the thread revision only after all completed responses are recorded.
6. Preserve partial failures as explicit room statuses rather than dropping the whole forum round.

The forum message schema should look like:

```json
{
  "id": "fmsg-123",
  "thread_id": "forum-sync",
  "room_id": "room-security",
  "author_type": "chymeria",
  "author_id": "card-hermit",
  "kind": "decision",
  "body": "The security room recommends signed, revisioned packets.",
  "packet": {
    "room_id": "room-security",
    "revision": 2,
    "position": "Use signed, revisioned packets",
    "confidence": "high",
    "unresolved_questions": ["How should replay be handled?"]
  },
  "reply_to": null,
  "thread_revision": 1
}
```

Use a stable packet hash/idempotency key such as `sha256(thread_id + room_id + packet.revision + packet.position)` for duplicate suppression. Treat JSON state writes as the first persistence backend, but isolate the storage functions so SQLite/event-log migration remains possible.

**Step 4: Run tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_forum_allows_room_chymeria_replies_without_private_transcript_leak tests.test_runtime.RuntimeContractTests.test_forum_round_is_idempotent -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/forum_runtime.py backend/main.py tests/test_runtime.py
 git commit -m "feat: connect room Chymeria agents through forum threads"
```

---

## Task 6: Add Rooms and Forum UI controls

**Objective:** Make rooms, hands/spreads, Chymeria identity, and forum communication usable from the OBus desktop dashboard.

**Files:**
- Modify: `backend/static/index.html`
- Modify: `tests/test_runtime.py`

**Step 1: Write failing UI contract tests**

Assert that the HTML contains:

- navigation IDs/pages `rooms` and `forum`
- `room-list`, `room-dialog`, `room-name`, `room-card-picker`, `room-mode`, `room-chymeria`, `save-room`
- `forum-thread-list`, `forum-message-list`, `forum-round`, `forum-composer`, `send-forum-message`
- visible labels explaining that cards are private room seats and Chymeria is the public room voice

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_rooms_and_forum_ui_have_real_controls -v
```

Expected: FAIL because the new controls do not exist.

**Step 3: Implement the UI**

Add a Rooms page with:

- Create/edit room modal.
- Multi-select card picker sourced from `/api/cards`.
- Mode selector: Collaborative / Adversarial.
- Chymeria card and ready-Key selectors.
- Room status, latest revision, selected hand, and private-run button.
- A concise room decision view; raw room transcript stays behind an explicit expand action.

Add a Forum page with:

- Thread creation from selected rooms.
- Timeline showing only Chymeria authors.
- Packet metadata: room, revision, confidence, status, unresolved questions.
- `Run forum round` button and per-room progress/failure indicators.
- Reply composer addressed to a room or broadcast to the thread.

Use the existing `api()` helper, `escapeHtml()`, toast handling, and refresh pattern. Do not use simulated alerts or hard-coded successful results. Render all server state as untrusted text.

**Step 4: Run tests to verify pass**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_rooms_and_forum_ui_have_real_controls -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/static/index.html tests/test_runtime.py
 git commit -m "feat: add OBus rooms and forum dashboard"
```

---

## Task 7: Connect rooms to MemoryHub, Tarot Router, and Solomon's Keys

**Objective:** Make room context, routing, and provider readiness visible and safe without changing existing global routing behavior.

**Files:**
- Modify: `backend/room_runner.py`
- Modify: `backend/forum_runtime.py`
- Modify: `backend/memory_hub.py` only if a read-only room/forum adapter is needed
- Modify: `backend/main.py`
- Test: `tests/test_runtime.py`

**Step 1: Write failing tests**

Verify:

- Room prompts include room-local MemoryHub results only when RAG is enabled.
- Forum prompts include forum decision packets but not private room messages.
- A staged Key is shown in the registry but cannot execute a card or Chymeria.
- Existing `/api/route/plan` and `/api/route/run` responses remain backward-compatible.
- Room assignments include `llm_key`, provider, model, context window, and pairing mode, but never secret values.
- A forum round respects the Tarot Router's ready/staged states and bounded parallelism.

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_room_and_forum_context_respect_visibility_and_key_readiness -v
```

Expected: FAIL until the new prompt assembly and readiness checks are wired.

**Step 3: Implement routing integration**

Reuse `match_cards_to_keys()` for room seats, but add room-specific filtering so manual card pairing cannot bypass readiness. Use the configured Chymeria key only if it is ready and connected; otherwise return a clear blocked status and remediation message.

Add a `context_manifest` to room/forum runs recording source IDs and character counts. This makes provenance auditable without copying large private text into public packets.

Keep the existing global aggregator behavior untouched. A forum thread may optionally nominate its own Chymeria aggregator, but the default should be “each room speaks; no hidden global synthesis.”

**Step 4: Run tests to verify pass**

```bash
python -m unittest tests.test_runtime -v
```

Expected: all existing tests plus the new room/forum tests pass.

**Step 5: Commit**

```bash
git add backend/main.py backend/room_runner.py backend/forum_runtime.py backend/memory_hub.py tests/test_runtime.py
 git commit -m "feat: route room councils through safe OBus integrations"
```

---

## Task 8: Add documentation, migration notes, and operational safeguards

**Objective:** Document the room/forum contract and protect users from accidental fan-out, context blowups, and secret leakage.

**Files:**
- Create: `docs/agentcouncil-rooms.md`
- Modify: `README_OBUS_EXE.md`
- Modify: `tests/test_runtime.py`

**Step 1: Write failing documentation/contract tests**

Assert that the documentation contains the canonical terms, endpoint names, privacy boundary, and both modes. Add a test that state migration from an old state file preserves existing cards, keys, settings, and memory integrations while adding empty room/forum collections.

**Step 2: Run tests to verify failure**

```bash
python -m unittest tests.test_runtime.RuntimeContractTests.test_agentcouncil_room_docs_and_state_migration -v
```

Expected: FAIL until docs and migration coverage exist.

**Step 3: Write the documentation**

`docs/agentcouncil-rooms.md` should include:

- Architecture diagram: card seats -> private room transcript -> Chymeria packet -> forum -> other Chymeria packets.
- Collaborative and adversarial phase diagrams.
- JSON examples for room, message, decision packet, and forum thread.
- REST endpoint table.
- Readiness and Solomon's Key rules.
- Complexity gate and parallelism limits.
- Recovery behavior for partial room failures.
- Explicit statement that AgentCouncil's Copilot CLI files are protocol inspiration; OBus does not require Copilot CLI to run.
- Source links: AgentCouncil README, skill, agent, and OBus files implementing the adapter.

Add operational safeguards:

- maximum rooms, cards per room, forum participants, packet size, and run timeout constants
- idempotency for room runs and forum rounds
- redaction tests for credentials and private prompts
- no automatic account creation, provider cycling, or staged-key activation
- archived rooms cannot be invoked or joined to new threads

**Step 4: Run validation**

```bash
python -m unittest tests.test_runtime -v
python -m compileall backend obus_launcher.py
```

Expected: all tests pass and Python compilation completes without errors.

**Step 5: Commit**

```bash
git add docs/agentcouncil-rooms.md README_OBUS_EXE.md tests/test_runtime.py
 git commit -m "docs: document AgentCouncil rooms and forum boundaries"
```

---

## Task 9: End-to-end verification and build decision

**Objective:** Prove the room/forum flow works through the OBus HTTP app before deciding whether to rebuild the Windows EXE.

**Files:**
- Modify only if verification exposes defects: files from Tasks 1-8
- Do not modify generated artifacts until source verification passes

**Step 1: Run the complete backend test suite**

```bash
python -m unittest discover -s tests -v
```

Expected: all existing OBus tests and all new room/forum tests pass.

**Step 2: Exercise an HTTP integration scenario**

Using `TestClient` or a local dev server:

1. Create Room A with three cards in collaborative mode.
2. Create Room B with three different cards in adversarial mode.
3. Create a forum thread containing A and B.
4. Run both rooms with a mocked deterministic adapter.
5. Run one forum round.
6. Assert that each room has one Chymeria decision packet and the forum has two room-authored replies.
7. Assert that Room A's private transcript does not appear in Room B's response or public forum payload.
8. Repeat the forum round and confirm no duplicate packet is created.

**Step 3: Run static and security checks**

```bash
python -m compileall backend obus_launcher.py
python -m unittest tests.test_runtime.RuntimeContractTests.test_no_room_or_forum_response_contains_secret_fields -v
```

Expected: PASS.

**Step 4: Verify the desktop app manually only after source tests pass**

Start the existing launcher, open the Rooms page, create two rooms, open a forum thread, run with the local ready Key, and confirm status transitions are real (`idle` -> `running` -> `complete` or explicit `blocked`/`failed`). Confirm the browser UI does not claim completion when the backend fails.

**Step 5: Rebuild only if the source artifact is verified**

Use the repository's existing PyInstaller spec and `SKILL.md` verification checklist. Do not copy a legacy EXE. Verify source timestamp, output timestamp, file hash, launch URL, and the new Rooms/Forum controls before reporting a new build.

---

## Likely Files to Change Summary

- Create: `backend/room_models.py`
- Create: `backend/room_council.py`
- Create: `backend/room_runner.py`
- Create: `backend/forum_runtime.py`
- Create: `docs/agentcouncil-rooms.md`
- Modify: `backend/main.py`
- Modify: `backend/static/index.html`
- Modify: `tests/test_runtime.py`
- Modify: `README_OBUS_EXE.md`
- Do not intentionally edit: `dist/OBus.exe`, `build/OBus/*`, or generated `__pycache__` files until source behavior is fully tested.

## Risks, Tradeoffs, and Open Questions

- **Meaning of “hand/set”:** This plan treats it as a user-selected list of existing Tarot card IDs. If the intended meaning is a separate named spread schema with positions such as obstacle/advice/outcome, add `spread_positions` to the room model before Task 2.
- **Meaning of “Chymeria”:** This plan treats it as one logical representative context per room, not necessarily one long-lived OS process. If it must be a persistent external agent process, add a process supervisor and health protocol after the REST MVP.
- **Persistence:** JSON is consistent with current OBus state but is vulnerable to concurrent writes. If forum rounds become frequent or multi-process, migrate room/forum event storage to SQLite with append-only messages and optimistic revision checks.
- **Parallelism:** Card calls within a room and room representatives within a forum round can run in parallel, but the Tarot Router's bounded capacity and provider cooldowns must remain authoritative. Never launch one task per card without a limit.
- **Provider diversity:** AgentCouncil prefers different model families; OBus may only have one ready local Key. In that case use a smaller council and report reduced diversity rather than duplicating or bypassing Keys.
- **Prompt leakage:** A Chymeria packet must be a deliberate summary, not a raw transcript dump. Add packet-size and field allowlists before enabling cross-room forum rounds.
- **Streaming:** REST polling is simpler and matches existing job endpoints. WebSockets/SSE should be a later optimization, not a prerequisite for correctness.
- **License/vendor policy:** The AgentCouncil README says MIT, but the GitHub API response did not expose a license object. Before copying any upstream file into OBus, verify the repository's license file/metadata and prefer implementing the protocol from scratch with source attribution.

## Acceptance Criteria

- A user can create multiple isolated rooms, each with a distinct hand/spread and one Chymeria representative.
- Each room can run collaborative or adversarial AgentCouncil-style phases.
- Each room produces one structured, versioned decision packet representing the whole room.
- Room representatives can exchange packets in a forum and reply to one another.
- Private card transcripts never cross room boundaries by default.
- Existing OBus routing, Keys, MemoryHub, dashboard, and tests remain functional.
- Staged or unverified provider Keys cannot execute room work.
- Repeated runs and forum rounds are idempotent or explicitly revisioned.
- UI status reflects real backend execution and failure states.
- The implementation is covered by automated tests and an end-to-end two-room scenario.
