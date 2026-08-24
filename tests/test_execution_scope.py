import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend


class ExecutionScopeTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(backend.app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "state.json"
        self.state_patch = patch.object(backend, "STATE_FILE", self.state_file)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.tempdir.cleanup()

    def test_route_plan_labels_remote_aggregate_as_preview_without_prompt_transfer(self):
        state = backend.normalize_state({})
        state["settings"] = {"selected_model": "gpt-oss:20b"}
        remote_aggregator = next(key for key in state["keys"] if key["id"] == "key-codex-oauth")
        remote_aggregator["local"] = False
        state["aggregation_explicit"] = True
        state["aggregator_key_id"] = remote_aggregator["id"]
        backend.save_state(state)

        response = self.client.post(
            "/api/route/plan",
            json={"prompt": "Review the architecture", "rag_enabled": False},
        )

        self.assertEqual(response.status_code, 200)
        scope = response.json()["execution_scope"]
        self.assertEqual(scope["mode"], "preview_only")
        self.assertFalse(scope["remote_prompt_transfer"])
        self.assertTrue(any(stage["preview"] for stage in scope["stages"]))
        self.assertNotIn("api_key", str(scope).lower())

    def test_route_run_requires_confirmation_before_remote_aggregate(self):
        state = backend.normalize_state({})
        state["settings"] = {"selected_model": "gpt-oss:20b"}
        remote_aggregator = next(key for key in state["keys"] if key["id"] == "key-codex-oauth")
        remote_aggregator.update(local=False, verified=True, approved=True, state="ready")
        state["aggregation_explicit"] = True
        state["aggregator_key_id"] = remote_aggregator["id"]
        backend.save_state(state)

        ollama = {"connected": True, "models": ["gpt-oss:20b"], "runtime_contexts": {"gpt-oss:20b": 131072}, "model_contexts": {}}
        statuses = [{"id": "key-codex-oauth", "connected": True}]
        with patch.object(backend, "get_ollama_status", return_value=ollama), patch.object(backend, "provider_statuses", return_value=statuses), patch.object(backend, "build_moa_router_command", return_value=None), patch.object(backend, "generate_with_ollama", return_value=("local answer", {})), patch.object(backend, "AGGREGATE_WITH_KEY") as aggregate:
            response = self.client.post("/api/route/run", json={"prompt": "Review architecture", "rag_enabled": False, "harness_enabled": False})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["execution_scope"]["remote_prompt_transfer"])
        self.assertEqual(response.json()["execution_scope"]["mode"], "confirmation_required")
        aggregate.assert_not_called()

    def test_route_ui_exposes_explicit_remote_execution_confirmation(self):
        html = self.client.get("/").text
        self.assertIn('id="confirm-remote-execution"', html)
        self.assertIn("confirm_remote_execution", html)


if __name__ == "__main__":
    unittest.main()
