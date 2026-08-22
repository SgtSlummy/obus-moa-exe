# AgentCouncil Rooms in OBus

OBus integrates the protocol ideas from [Sentry01/AgentCouncil](https://github.com/Sentry01/AgentCouncil) without requiring GitHub Copilot CLI. AgentCouncil is a markdown-only Copilot skill/agent; OBus ports its execution protocol into the existing Tarot persona, Solomon's Key, MemoryHub, and Tarot Router layers.

## Mental model

```text
Tarot cards in one hand/spread
        │ private room transcript
        ▼
room council: drafts → improve/attack → Chymeria synthesis
        │ one versioned public decision packet
        ▼
forum thread: Chymeria A ↔ Chymeria B ↔ Chymeria C
```

A hand/spread is an ordered set of existing Tarot card IDs. A room owns that hand, its mode, its private messages, and one Chymeria representative. Chymeria is a logical room-level agent context, not an additional permanent provider process. It speaks for the room only after the room council has produced a synthesis or verdict.

Other rooms do not receive raw card drafts, hidden prompts, provider errors, or credentials. They receive only the structured decision packet:

```json
{
  "room_id": "room-security",
  "revision": 2,
  "position": "Use signed, revisioned packets",
  "confidence": "high",
  "rationale": "...",
  "evidence_refs": [],
  "unresolved_questions": ["How should replay be handled?"],
  "requested_responses": [],
  "status": "approved"
}
```

## Room modes

Collaborative mode follows AgentCouncil's default protocol:

1. Each selected Tarot seat drafts independently.
2. Each seat reads the other seats' room-local drafts and improves its position.
3. Chymeria synthesizes one room decision packet.

Adversarial mode follows the stress-test protocol:

1. Each selected Tarot seat drafts independently.
2. The room triages a leading position.
3. Non-leading seats attack the leading position.
4. Chymeria delivers a verdict and records whether the position survived, was modified, or was overturned.

The complexity gate short-circuits obvious one-step prompts. If no ready and connected Key is available, the room is blocked rather than silently activating a staged Key or rotating accounts.

## API contract

| Endpoint | Purpose |
|---|---|
| `POST /api/rooms` | Create a room from a Tarot hand/spread |
| `GET /api/rooms` | List public room metadata |
| `GET /api/rooms/{room_id}` | Inspect one room without private messages |
| `PUT /api/rooms/{room_id}` | Edit an active room |
| `DELETE /api/rooms/{room_id}` | Archive a room |
| `GET /api/rooms/{room_id}/messages` | Read that room's private transcript |
| `POST /api/rooms/{room_id}/run` | Run its council and create one Chymeria packet |
| `POST /api/forum/threads` | Create a forum for two or more rooms |
| `GET /api/forum/threads` | List forum threads |
| `GET /api/forum/threads/{thread_id}` | Read public Chymeria messages |
| `POST /api/forum/threads/{thread_id}/messages` | Post a public room question |
| `POST /api/forum/threads/{thread_id}/round` | Let participating Chymeria representatives respond |

Forum rounds are revisioned and idempotent. Replaying a round with unchanged room revisions returns the existing messages instead of creating duplicates.

## Provider and memory boundaries

- Room seats and Chymeria use the same ready/connected Solomon's Key policy as global OBus routing.
- Key records store authorization references and environment-variable names, never raw secrets.
- The room runner uses the existing local Ollama/MoA execution boundary.
- MemoryHub context is room-local during a room run. Forum prompts may include public packets from other rooms, not private transcripts.
- The forum does not silently invoke the global aggregator. An optional higher-level synthesis can be added later as an explicit user action.

## UI flow

1. Open **Rooms** and choose **New room**.
2. Select a private Tarot hand/spread and choose Collaborative or Adversarial mode.
3. Choose the Chymeria card; OBus chooses a ready Solomon's Key.
4. Run the room and inspect its revisioned decision.
5. Open **Forum**, create a thread with two or more rooms, and run a forum round.
6. Read the Chymeria-to-Chymeria timeline. Raw card deliberation remains available only from the room view.

## Source and attribution

- AgentCouncil README: https://github.com/Sentry01/AgentCouncil
- AgentCouncil protocol skill: https://raw.githubusercontent.com/Sentry01/AgentCouncil/main/skills/agent-council/skill.md
- AgentCouncil standalone agent: https://raw.githubusercontent.com/Sentry01/AgentCouncil/main/agents/AgentCouncil.agent.md
- OBus models: `backend/room_models.py`
- OBus phase planner: `backend/room_council.py`
- OBus room runner: `backend/room_runner.py`
- OBus forum helpers: `backend/forum_runtime.py`
- OBus HTTP/UI integration: `backend/main.py` and `backend/static/index.html`

The upstream README states MIT, but OBus does not vendor upstream files. It implements the documented protocol locally and keeps the source links for provenance.
