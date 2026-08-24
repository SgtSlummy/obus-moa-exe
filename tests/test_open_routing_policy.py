import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend


class OpenRoutingPolicyTests(unittest.TestCase):
    def _state(self):
        state = backend.normalize_state({})
        state["cards"] = copy.deepcopy(state["cards"][:3])
        open_key = {
            "id": "key-open-test",
            "name": "Open Test Model",
            "provider": "open-test",
            "model": "open-model",
            "base_url": "http://127.0.0.1:9999/v1",
            "state": "ready",
            "verified": True,
            "approved": True,
            "active": True,
            "connected": True,
            "open_model": True,
            "local": False,
            "can_aggregate": False,
            "capabilities": ["analysis", "coding", "research"],
            "max_context_tokens": 32768,
        }
        closed_key = copy.deepcopy(open_key)
        closed_key.update(id="key-closed-test", name="Closed Test", open_model=False, model="closed-model")
        state["keys"].extend([open_key, closed_key])
        state["aggregator_key_id"] = "key-codex-oauth"
        return state

    def test_auto_open_uses_only_ready_connected_open_keys_and_never_persists_bindings(self):
        state = self._state()
        before = json.dumps(state["cards"], sort_keys=True)
        statuses = [
            {"id": "key-local-ollama", "connected": True},
            {"id": "key-open-test", "connected": True},
            {"id": "key-closed-test", "connected": True},
        ]
        with patch.object(backend, "provider_statuses", return_value=statuses):
            assignments = backend.match_cards_to_keys(state["cards"], state, "analyze and code", routing_policy="auto-open")
        self.assertTrue(assignments)
        self.assertTrue(all(item["llm_key"] in {"key-local-ollama", "key-open-test", "key-offline-room"} for item in assignments))
        self.assertTrue(all("routing_explanation" in item for item in assignments))
        self.assertEqual(before, json.dumps(state["cards"], sort_keys=True))

    def test_auto_open_returns_honest_offline_assignments_without_open_provider(self):
        state = self._state()
        state["keys"] = [key for key in state["keys"] if key["id"] == "key-codex-oauth"]
        with patch.object(backend, "provider_statuses", return_value=[]):
            assignments = backend.match_cards_to_keys(state["cards"], state, "research", routing_policy="auto-open")
        self.assertTrue(assignments)
        self.assertTrue(all(item["pairing_mode"] == "offline" for item in assignments))
        self.assertIn("auto-open", assignments[0]["routing_explanation"]["policy"])

    def test_api_plan_reports_selected_open_policy_and_explanation(self):
        client = TestClient(backend.app)
        with tempfile.TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            with patch.object(backend, "STATE_FILE", state_file), patch.object(
                backend, "get_ollama_status", return_value={"connected": False, "models": []}
            ):
                backend.save_state(backend.normalize_state({"settings": {"routing_policy": "auto-open"}}))
                response = client.post("/api/route/plan", json={"prompt": "Research an open model", "rag_enabled": False})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["routing_policy"], "auto-open")
        self.assertTrue(payload["agents"]["dynamic_assignments"])
        self.assertIn("routing_explanation", payload["agents"]["dynamic_assignments"][0])

    def test_key_editor_exposes_explicit_open_model_classification(self):
        html = TestClient(backend.app).get("/").text
        self.assertIn('id="key-open-model"', html)
        self.assertIn("open_model", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
