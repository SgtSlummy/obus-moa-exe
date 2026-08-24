import json
from threading import Barrier
from unittest.mock import patch

import backend.main as backend


def test_auto_deliberation_enabled(client):
    enabled = client.put("/api/settings/auto-deliberation", json={"enabled": True})
    assert enabled.status_code == 200
    assert enabled.json() == {"enabled": True}
    assert client.get("/api/settings/auto-deliberation").json() == {"enabled": True}

    with patch.object(backend, "ROOM_COMPLETE", backend.offline_room_complete), \
         patch.object(backend, "room_provider_ready", return_value=True):
        resp = client.post("/api/deliberate", json={"prompt": "Design a secure multi-agent workflow"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["room_ids"]) == 2
    assert len(data["card_sets"]) == 2
    assert all(data["card_sets"])
    assert len(data["round_results"]) == 2
    assert all(item["plan"]["card_ids"] for item in data["round_results"])
    assert all(item["assignments"] for item in data["round_results"])
    assert data["thread"]["status"] == "complete"
    assert any(message["kind"] == "prompt" for message in data["thread"]["messages"])

    assert client.get(f"/api/rooms/{data['room_ids'][0]}").status_code == 200
    persisted = client.get("/api/forum/threads").json()
    assert any(thread["id"] == data["thread_id"] for thread in persisted)


def test_auto_deliberation_disabled(client):
    disabled = client.put("/api/settings/auto-deliberation", json={"enabled": False})
    assert disabled.status_code == 200
    resp = client.post("/api/deliberate", json={"prompt": "Test"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Auto deliberation is disabled"


def test_explicit_plan_is_side_effect_free_and_does_not_enable_auto_mode(client):
    before = backend.load_state()
    before_rooms = {room["id"] for room in before.get("rooms", [])}
    before_threads = {thread["id"] for thread in before.get("forum_threads", [])}
    response = client.post("/api/plan/deliberate", json={"prompt": "Plan a safe rollout for a multi-agent service"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "multi-agent-plan"
    assert payload["execution"] == "planning-only"
    assert payload["deliberation"]["parallel"] is True
    assert len(payload["deliberation"]["room_ids"]) == 2
    assert payload["deliberation"]["thread"]["status"] == "planned"
    after = backend.load_state()
    assert {room["id"] for room in after.get("rooms", [])} == before_rooms
    assert {thread["id"] for thread in after.get("forum_threads", [])} == before_threads


def test_plan_route_serves_the_visual_plan_workbench(client):
    response = client.get("/plan")

    assert response.status_code == 200
    assert 'id="plan-workbench"' in response.text


def test_room_proposals_dispatch_in_parallel(client):
    state = backend.load_state()
    room = {
        "id": "room-parallel", "name": "Parallel room", "card_ids": ["card-hermit", "card-magician"],
        "mode": "collaborative", "chymeria": {"card_id": "card-hermit", "key_id": "key-local-ollama"}, "revision": 0,
    }
    draft_barrier = Barrier(2, timeout=2)

    def complete(**kwargs):
        if kwargs["phase"] == "draft":
            draft_barrier.wait()
        return json.dumps({
            "position": f"{kwargs['phase']} proposal", "confidence": "high", "rationale": "test",
            "evidence_refs": [], "unresolved_questions": [], "requested_responses": [], "status": "approved",
        })

    result = backend.run_room_council(
        room, state, "Plan a resilient multi-agent release", complete,
        lambda key: key.get("id") == "key-local-ollama",
    )

    assert [message["phase"] for message in result["private_messages"]] == ["draft", "draft", "improve", "improve", "synthesize"]


def test_room_seats_do_not_nest_the_moa_router():
    assignment = {"llm_key": "key-local-ollama", "model": "gpt-oss:20b"}
    with patch.object(backend, "build_moa_router_command") as nested_router, \
         patch.object(backend, "generate_with_ollama", return_value=("proposal", {})) as completion:
        output = backend.default_room_complete(assignment=assignment, prompt="Plan a safe rollout")

    assert output == "proposal"
    nested_router.assert_not_called()
    completion.assert_called_once()


def test_enabled_auto_deliberation_enriches_a_hermes_route_without_executing_tools(client):
    state = backend.load_state()
    state["runtime_settings"]["auto_deliberation"] = True
    backend.save_state(state)
    deliberation = {
        "thread_id": "forum-route-plan", "room_ids": ["room-a", "room-b"],
        "round_results": [
            {"decision_packet": {"room_id": "room-a", "position": "Use a staged rollout.", "confidence": "high", "status": "approved"}},
            {"decision_packet": {"room_id": "room-b", "position": "Verify rollback before expansion.", "confidence": "medium", "status": "approved"}},
        ],
    }
    with patch.object(backend, "execute_auto_deliberation", return_value=deliberation) as execute, \
         patch.object(backend, "get_ollama_status", return_value={"connected": False, "models": []}):
        response = client.post("/api/route/run", json={"prompt": "Plan a safe staged service rollout", "rag_enabled": False})

    assert response.status_code == 200
    payload = response.json()
    assert payload["engine"] == "offline-planner"
    assert payload["deliberation"]["status"] == "complete"
    assert payload["deliberation"]["parallel"] is True
    assert payload["deliberation"]["room_ids"] == ["room-a", "room-b"]
    assert "private_messages" not in json.dumps(payload["deliberation"])
    execute.assert_called_once()


def test_auto_deliberation_supplies_only_bounded_public_evidence_to_local_synthesis(client):
    state = backend.load_state()
    state["runtime_settings"]["auto_deliberation"] = True
    backend.save_state(state)
    deliberation = {
        "thread_id": "forum-route-plan", "room_ids": ["room-a"],
        "round_results": [{"decision_packet": {
            "room_id": "room-a", "position": "Roll out gradually after rollback verification.",
            "confidence": "high", "status": "approved", "rationale": "public rationale",
        }}],
    }
    ollama = {"connected": True, "models": ["gpt-oss:20b"], "runtime_contexts": {}, "model_contexts": {}}
    with patch.object(backend, "execute_auto_deliberation", return_value=deliberation), \
         patch.object(backend, "get_ollama_status", return_value=ollama), \
         patch.object(backend, "build_moa_router_command", return_value=None), \
         patch.object(backend, "generate_with_ollama", return_value=("local answer", {})) as synthesize:
        response = client.post("/api/route/run", json={"prompt": "Plan a safe staged service rollout", "rag_enabled": False, "harness_enabled": False})

    assert response.status_code == 200
    supplied_prompt = synthesize.call_args.args[0]
    assert "<obus_parallel_deliberation>" in supplied_prompt
    assert "Roll out gradually after rollback verification." in supplied_prompt
    assert "private_messages" not in supplied_prompt
