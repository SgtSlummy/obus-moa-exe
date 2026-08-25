import asyncio
import threading

from backend import main as backend


def test_stop_persistent_agent_is_immediately_terminal(monkeypatch):
    agent = {"id": "agent-cancel-test", "status": "running"}
    state = {"persistent_agents": [agent]}
    saved = []

    monkeypatch.setattr(backend, "load_state", lambda: state)
    monkeypatch.setattr(backend, "save_state", lambda value: saved.append(value))
    backend.PERSISTENT_AGENT_STOP_EVENTS[agent["id"]] = threading.Event()

    try:
        result = asyncio.run(backend.stop_persistent_agent(agent["id"]))

        assert backend.PERSISTENT_AGENT_STOP_EVENTS[agent["id"]].is_set()
        assert result["status"] == "stopped"
        assert state["persistent_agents"][0]["status"] == "stopped"
        assert saved == [state]
    finally:
        backend.PERSISTENT_AGENT_STOP_EVENTS.pop(agent["id"], None)
