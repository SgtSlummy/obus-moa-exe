# Auto‑Deliberation Implementation Plan
> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task.

## Goal
Add a togglable `auto_deliberation` flag that, when enabled, automatically creates a forum thread and room for any incoming `/api/deliberate` prompt, runs the Tarot‑Router policy, and stores the deliberation conversation.

## Architecture
* Add runtime flag to `normalize_state`.
* Expose REST endpoints (`GET/PUT /api/settings/auto-deliberation`).
* Implement `/api/deliberate` handler that:
  1. Creates forum thread via existing `create_forum_thread`.
  2. Creates room via existing `create_room`.
  3. Adds the prompt as a room message.
  4. Calls `run_room`.
* Integration tests validate the flow end‑to‑end.

## Tech Stack
* Backend: **Python 3.10+**, FastAPI, Uvicorn.
* State persistence: JSON file (`obus_state.json`).
* Tests: pytest, httpx.
* Linting: flake8 (kept dry).

## Files Likely to Change
| Action | File |
|--------|------|
| Add flag to `normalize_state` | `backend/main.py` |
| Read flag from env | `backend/main.py` |
| Add endpoints | `backend/main.py` |
| Implement `/api/deliberate` | `backend/main.py` |
| Update tests | `tests/test_settings.py`, `tests/test_deliberate.py` |
| Add new test helpers | `tests/conftest.py` (for state setup) |
| Update documentation | `docs/api.md` (optional) |

## Step‑by‑Step Plan

### Task 1: Add `auto_deliberation` flag to state
```diff
--- backend/main.py
+++ backend/main.py
@@
-    state.setdefault("runtime_settings", {})
-    state["runtime_settings"]["auto_deliberation"] = bool(os.getenv("OBUS_AUTO_DELIBERATION", "false").lower() == "true")
+    state.setdefault("runtime_settings", {})
+    state.setdefault("runtime_settings", {})
+    state["runtime_settings"]["auto_deliberation"] = bool(os.getenv("OBUS_AUTO_DELIBERATION", "false").lower() == "true")
```
*Verify*: Reload the app; GET `/api/settings` should now include "auto_deliberation": false (or true if env set).

### Task 2: Expose REST endpoints
```python
@app.get("/api/settings/auto-deliberation")
async def get_auto_deliberation() -> dict[str, bool]:
    state = load_state()
    return {"enabled": bool(state.get("runtime_settings", {}).get("auto_deliberation", False))}

@app.put("/api/settings/auto-deliberation")
async def set_auto_deliberation(body: dict[str, bool]) -> dict[str, bool]:
    state = load_state()
    state.setdefault("runtime_settings", {})
    state["runtime_settings"]["auto_deliberation"] = bool(body.get("enabled", False))
    save_state(state)
    return {"enabled": state["runtime_settings"]["auto_deliberation"]}
```
*Verify*: `PUT /api/settings/auto-deliberation` changes persisted state.

### Task 3: Implement `/api/deliberate` handler
```python
@app.post("/api/deliberate")
async def deliberation_prompt(prompt: str = Body(..., embed=True)) -> dict:
    state = load_state()
    if not state.get("runtime_settings", {}).get("auto_deliberation"):
        raise HTTPException(status_code=400, detail="Auto deliberation is disabled")
    # 1. Create forum thread
    thread = await create_forum_thread(ForumThreadCreate(title=prompt[:50], description=prompt))
    thread_id = thread["thread_id"]
    # 2. Create room
    room_create = RoomCreate(title=f"Auto‑Room {thread_id}")
    room = await create_room(room_create)
    room_id = room["id"]
    # 3. Add prompt as first message
    await add_room_message(room_id, {"body": prompt, "author_type": "user", "author_id": "system"})
    # 4. Run deliberation
    result = await run_room(room_id, RoomRunRequest(message=prompt))
    return {"room_id": room_id, "thread_id": thread_id, **result}
```
*Verify*: POST a prompt, check returned JSON includes `room_id`, `thread_id`, and deliberation packet.

### Task 4: Create integration tests (`tests/test_deliberate.py`)
```python
import pytest
from httpx import AsyncClient
from main import app  # import the FastAPI app

@pytest.mark.asyncio
async def test_auto_deliberation_enabled():
    # Enable flag
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.put("/api/settings/auto-deliberation", json={"enabled": True})
        resp = await ac.post("/api/deliberate", json={"prompt": "Test prompt"})
    assert resp.status_code == 200
    data = resp.json()
    assert "room_id" in data and "thread_id" in data
    # Ensure room exists
    r = await ac.get(f"/api/rooms/{data['room_id']}")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_auto_deliberation_disabled():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        await ac.put("/api/settings/auto-deliberation", json={"enabled": False})
        resp = await ac.post("/api/deliberate", json={"prompt": "Test"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Auto deliberation is disabled"
```

### Task 5: Create test helper in `tests/conftest.py` (optional)
```python
@pytest.fixture
def client():
    from main import app
    from backend.main import save_state, load_state
    # Reset state before each test
    load_state().clear()
    save_state({})
    from httpx import AsyncClient
    return AsyncClient(app=app, base_url="http://test")
```

### Task 6: Run full test suite
```bash
pytest tests/test_deliberate.py -v
```
All tests should pass, indicating the flag and endpoint work.

### Task 7: Verify persistence
```bash
# Start app with auto flag true
uvicorn backend.main:app --reload
# Use curl or httpx to POST /api/deliberate
curl -X POST http://localhost:8000/api/deliberate -d '{"prompt":"Check"}'
# Restart app
# GET /api/settings/auto-deliberation should still return enabled:true
```

### Task 8: Documentation (optional)
Add a snippet to `docs/api.md` describing the new endpoint and flag.

```markdown
### Auto‑Deliberation Settings

* `GET /api/settings/auto-deliberation` – returns current state.
* `PUT /api/settings/auto-deliberation` – toggles auto‑deliberation.
* `POST /api/deliberate` – creates a new room/threads automatically when flag is enabled.
```

## Risks & Trade‑offs
* **State corruption** – ensure atomic write to `obus_state.json`. We already use `save_state` which writes temp file.
* **Race conditions** – `run_room` handles room locking; new flow uses same endpoints, so no additional concurrency issues.
* **Performance** – Adding threads/rooms incurs minimal overhead; the heavy lifting remains with the selected LLM key. GPU acceleration via Ollama remains unchanged.
* **Security** – Flag is toggleable at runtime; no new credentials required.

## Open Questions
* Do we want an extra field in the response for the number of deliberation packets?  
* Should we expose a `DELETE /api/deliberate/{room_id}` to clean up auto‑created rooms?  
* Do we need metrics for how often auto‑deliberation is triggered? (This could be added later.)

---

### Save location
The plan will be written to `.hermes/plans/2026-08-24_204700-auto-deliberation.md`.

**Ready to run the plan** – you can dispatch a subagent via `subagent-driven-development` or implement the steps manually. Please let me know if you’d like me to initiate the subagents.
