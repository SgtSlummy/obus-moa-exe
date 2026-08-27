import json
import threading
import time

import backend.main as backend
from fastapi.testclient import TestClient
from backend.context_policy import bounded_agent_context, resolve_context_window
from backend.user_settings import normalize_user_settings


def test_context_window_uses_ninety_five_percent_of_detected_runtime_capacity():
    status = {"runtime_contexts": {"gpt-oss:20b": 32_768}, "model_contexts": {"gpt-oss:20b": 131_072}}
    settings = normalize_user_settings({})
    assert resolve_context_window("gpt-oss:20b", status, settings) == 124_518


def test_local_generation_sends_the_resolved_context_window_to_ollama(monkeypatch):
    state = backend.normalize_state({})
    state["settings"].update({"selected_model": "local:test", "context_utilization_percent": 95})
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return json.dumps({
                "response": "local answer", "prompt_eval_count": 12,
                "eval_count": 4, "total_duration": 1_000_000_000,
            }).encode("utf-8")

    class Opener:
        def open(self, request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return Response()

    monkeypatch.setattr(backend, "load_state", lambda: state)
    monkeypatch.setattr(backend, "get_ollama_status", lambda: {
        "runtime_contexts": {}, "model_contexts": {"local:test": 131_072}, "connected": True,
    })
    monkeypatch.setattr(backend, "_NO_REDIRECT_OPENER", Opener())

    answer, metrics = backend.generate_with_ollama("Inspect the workspace", "local:test", {
        "selected_deck": {"name": "Auto"}, "agents": {"dynamic_assignments": []},
    })

    assert answer == "local answer"
    assert metrics["context_window"] == 124_518
    assert captured["payload"]["options"]["num_ctx"] == 124_518
    assert captured["timeout"] == 180


def test_context_override_is_per_agent_and_clamped_to_model_capacity():
    status = {"runtime_contexts": {}, "model_contexts": {"local": 65_536}}
    assert resolve_context_window("local", status, {"per_agent_context_window": 32_768}) == 32_768
    assert resolve_context_window("local", status, {"per_agent_context_window": 500_000}) == 65_536


def test_bounded_agent_context_keeps_private_and_shared_context_separate():
    private, shared = bounded_agent_context(
        [{"step": 1, "output": "private result"}],
        [{"agent_name": "Researcher", "output": "shared evidence"}],
        4096,
    )
    assert "private result" in private
    assert "shared evidence" not in private
    assert "shared evidence" in shared


def test_parallel_agent_gate_honors_the_live_worker_limit():
    gate = backend._ParallelAgentGate(20)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first_worker():
        gate.acquire(1)
        try:
            first_entered.set()
            release_first.wait(timeout=1)
        finally:
            gate.release()

    def second_worker():
        gate.acquire(1)
        try:
            second_entered.set()
        finally:
            gate.release()

    first = threading.Thread(target=first_worker)
    second = threading.Thread(target=second_worker)
    first.start()
    assert first_entered.wait(timeout=1)
    second.start()
    deadline = time.monotonic() + 1
    while gate.snapshot()["queued"] != 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert gate.snapshot() == {"active": 1, "queued": 1, "maximum": 20}
    assert not second_entered.is_set()
    release_first.set()
    first.join(timeout=1)
    second.join(timeout=1)
    assert second_entered.is_set()
    assert gate.snapshot() == {"active": 0, "queued": 0, "maximum": 20}


def test_agent_prompt_includes_autonomy_budget_and_sibling_ledger(monkeypatch):
    state = backend.normalize_state({})
    state["settings"].update({"autonomy_level": "high", "shared_task_context": True})
    state["task_ledgers"] = [{
        "id": "task-one", "findings": [
            {"agent_id": "agent-other", "agent_name": "Researcher", "output": "validated sibling finding"},
        ],
    }]
    agent = {
        "id": "agent-one", "name": "Builder", "card_id": "card-magician", "objective": "Build it",
        "max_steps": 2, "current_model": "gpt-oss:20b", "current_key_id": "key-local-ollama",
        "task_ledger_id": "task-one", "history": [{"step": 1, "output": "private draft"}],
    }
    card = next(item for item in state["cards"] if item["id"] == "card-magician")
    monkeypatch.setattr(backend, "get_ollama_status", lambda: {
        "runtime_contexts": {"gpt-oss:20b": 131_072}, "model_contexts": {}, "connected": True,
    })
    prompt = backend._agent_prompt(agent, card, "Continue", 2, state)
    assert "context budget 124518 tokens" in prompt
    assert agent["context_window"] == 124_518
    assert 0 < agent["context_input_tokens_estimate"] <= agent["context_window"]
    assert agent["context_usage_source"] == "sanitized prompt estimate"
    assert "private draft" in prompt
    assert "validated sibling finding" in prompt
    assert "Ask only when credentials" in prompt


def test_route_usage_reports_the_effective_per_agent_context_window(monkeypatch):
    state = backend.normalize_state({})
    state["settings"].update({"selected_model": "local", "context_utilization_percent": 95})
    monkeypatch.setattr(backend, "load_state", lambda: state)
    monkeypatch.setattr(backend, "get_ollama_status", lambda: {
        "runtime_contexts": {}, "model_contexts": {"local": 100_000}, "connected": True,
    })
    monkeypatch.setattr(backend, "get_usage_summary", lambda context_window: {"context_window": context_window})
    response = TestClient(backend.app).get("/api/usage")
    assert response.status_code == 200
    assert response.json()["context_window"] == 95_000


def test_harness_runtime_config_uses_current_selected_model_and_per_agent_window(monkeypatch):
    state = backend.normalize_state({})
    state["settings"].update({"selected_model": "local:test", "per_agent_context_window": 49_152})
    monkeypatch.setattr(backend, "load_state", lambda: state)
    monkeypatch.setattr(backend, "get_ollama_status", lambda: {
        "runtime_contexts": {}, "model_contexts": {"local:test": 65_536}, "connected": True,
    })

    config = backend._resolve_harness_runtime_config({"provider": "ollama"})

    assert config == {"model": "local:test", "context_window": 49_152}


def test_orchestrator_persists_a_shared_task_ledger(client, monkeypatch):
    plan = {
        "agents": [{
            "name": "Researcher", "card_id": "card-hermit", "objective": "Research independently",
            "max_steps": 1, "auto_start": False,
        }],
        "rooms": [], "forums": [],
    }
    monkeypatch.setattr(backend, "PRIMARY_ORCHESTRATOR_COMPLETE", lambda **_: json.dumps(plan))
    response = client.post("/api/runtime/orchestrate", json={"objective": "Parallel task", "execute": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_ledger_id"].startswith("task-")
    ledger = client.get(f"/api/runtime/task-ledgers/{payload['task_ledger_id']}").json()
    assert ledger["objective"] == "Parallel task"
    assert ledger["agent_ids"] == [payload["created_agents"][0]["id"]]
    assert payload["created_agents"][0]["task_ledger_id"] == ledger["id"]
