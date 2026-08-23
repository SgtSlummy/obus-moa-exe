import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend


class IntegratedDashboardTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(backend.app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "obus_state.json"
        self.memory_file = Path(self.tempdir.name) / "memory.json"
        self.usage_file = Path(self.tempdir.name) / "usage.json"
        self.state_patch = patch.object(backend, "STATE_FILE", self.state_file)
        self.memory_patch = patch.object(backend, "MEMORY_FILE", self.memory_file, create=True)
        self.usage_patch = patch.object(backend, "USAGE_FILE", self.usage_file, create=True)
        self.state_patch.start()
        self.memory_patch.start()
        self.usage_patch.start()

    def tearDown(self):
        self.usage_patch.stop()
        self.memory_patch.stop()
        self.state_patch.stop()
        self.tempdir.cleanup()

    def test_dashboard_exposes_all_card_assignment_preview_and_safe_key_guides(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        harness = payload["harness"]
        self.assertEqual(len(harness["all_card_assignments"]), 78)
        self.assertTrue(all({"agent_id", "agent_title", "model", "llm_key", "pairing_mode"} <= set(item) for item in harness["all_card_assignments"]))
        self.assertTrue(all(item["pairing_mode"] in {"auto", "manual", "offline"} for item in harness["all_card_assignments"]))

        for provider in payload["providers"]:
            setup = provider["setup"]
            self.assertTrue(setup["docs_url"].startswith("https://"))
            self.assertTrue(setup["steps"])
            self.assertNotIn("secret_value", setup)

    def test_harness_preview_is_prompt_specific_without_persisting_card_key_bindings(self):
        response = self.client.post(
            "/api/harness/preview",
            json={"prompt": "Review a Python service for security and debugging"},
        )
        self.assertEqual(response.status_code, 200)
        preview = response.json()
        self.assertEqual(preview["prompt"], "Review a Python service for security and debugging")
        self.assertEqual(len(preview["all_card_assignments"]), 78)
        self.assertEqual(backend.load_state()["cards"][0]["assignment_mode"], "auto")

    def test_route_harness_is_injected_only_into_the_local_execution_prompt(self):
        captured = {}

        def local(prompt, model, plan):
            captured["prompt"] = prompt
            return "LOCAL", {"calls": 1}

        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["gpt-oss:20b"]}), \
             patch.object(backend, "provider_statuses", return_value=[{"id": "key-local-ollama", "connected": True}]), \
             patch.object(backend, "build_moa_router_command", return_value=None), \
             patch.object(backend, "generate_with_ollama", side_effect=local):
            response = self.client.post("/api/route/run", json={"prompt": "Analyze this service", "rag_enabled": False, "harness_enabled": True})

        self.assertEqual(response.status_code, 200)
        self.assertIn("<obus_agent_harness>", captured["prompt"])
        self.assertIn("Analyze this service", captured["prompt"])
        self.assertEqual(response.json()["final"], "LOCAL")

    def test_local_voice_endpoint_refuses_unconfigured_models_without_downloads(self):
        response = self.client.post("/api/voice/transcribe", json={"audio_base64": "AAAA", "mime_type": "audio/webm"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("OBUS_LOCAL_STT_MODEL_PATH", response.json()["detail"])
        self.assertNotIn("download", response.json()["detail"].lower())

    def test_build_spec_includes_local_voice_runtime_dependencies(self):
        spec = (Path(__file__).resolve().parents[1] / "OBus.spec").read_text(encoding="utf-8")
        self.assertIn('"faster_whisper"', spec)
        self.assertIn('"sounddevice"', spec)

    def test_machine_role_setup_persists_a_guide_only_tailscale_ssh_configuration(self):
        before = self.client.get("/api/machine-setup")
        self.assertEqual(before.status_code, 200)
        self.assertIsNone(before.json()["role"])

        response = self.client.put(
            "/api/machine-setup",
            json={"role": "worker", "label": "Loki", "peer_label": "Thor"},
        )
        self.assertEqual(response.status_code, 200)
        setup = response.json()
        self.assertEqual(setup["role"], "worker")
        self.assertEqual(setup["transport"], "tailscale-ssh")
        self.assertEqual(setup["mode"], "guide-only")
        self.assertTrue(setup["steps"])
        self.assertNotIn("private_key", json.dumps(setup).lower())
        self.assertEqual(json.loads(self.state_file.read_text(encoding="utf-8"))["machine_setup"]["role"], "worker")

    def test_integrated_ui_exposes_harness_key_help_voice_and_role_controls(self):
        html = self.client.get("/").text
        for control_id in (
            "harness-assignment-list",
            "harness-preview-prompt",
            "output-autoscroll",
            "key-setup-dialog",
            "key-setup-content",
            "voice-toggle",
            "voice-status",
            "machine-role",
            "machine-setup-status",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("function renderHarness", html)
        self.assertIn("function openKeySetup", html)
        self.assertIn("function syncOutputScroll", html)


if __name__ == "__main__":
    unittest.main()
