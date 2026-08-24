import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.local_studios as studios
import backend.main as backend


class LocalStudioIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(backend.app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "obus_state.json"
        self.state_patch = patch.object(backend, "STATE_FILE", self.state_file)
        self.state_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.tempdir.cleanup()

    def test_comfyui_status_is_loopback_only_and_secret_safe(self):
        with patch.dict("os.environ", {"COMFYUI_URL": "https://example.invalid"}, clear=False):
            with patch.object(studios, "_json_probe", return_value=(False, None)):
                payload = self.client.get("/api/integrations/comfyui").json()

        self.assertEqual(payload["url"], studios.DEFAULT_COMFYUI_URL)
        self.assertFalse(payload["reachable"])
        self.assertNotIn("api_key", json.dumps(payload).lower())

    def test_comfyui_status_reports_a_reachable_real_service_shape(self):
        with patch.object(studios, "_json_probe", return_value=(True, {"system": {"comfyui_version": "0.33.0", "device": "cpu"}})):
            payload = self.client.get("/api/integrations/comfyui").json()

        self.assertTrue(payload["reachable"])
        self.assertEqual(payload["version"], "0.33.0")
        self.assertEqual(payload["device"], "cpu")

    def test_understand_anything_context_is_bounded_to_graph_metadata(self):
        root = Path(self.tempdir.name) / "workspace"
        graph = root / ".ua" / "knowledge-graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text(json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}]}), encoding="utf-8")
        self.state_file.write_text(json.dumps({"settings": {"workspace_root": str(root)}}), encoding="utf-8")

        status = self.client.get("/api/integrations/understand-anything")
        context = self.client.post("/api/integrations/understand-anything/context")

        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.json()["graph_available"])
        self.assertEqual(status.json()["nodes"], 2)
        self.assertEqual(context.status_code, 200)
        self.assertIn("Structural nodes: 2", context.json()["context"])
        self.assertNotIn('"id": "a"', context.json()["context"])

    def test_studio_ui_exposes_real_status_and_context_controls(self):
        html = self.client.get("/").text
        for control_id in (
            "studio-refresh",
            "comfyui-status",
            "comfyui-start",
            "comfyui-open",
            "comfyui-frame",
            "understand-anything-status",
            "understand-anything-use",
            "understand-anything-open",
            "warp-status",
            "warp-launch",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("function loadStudios", html)
        self.assertIn("/api/integrations/comfyui/start", html)
        self.assertIn("/api/integrations/understand-anything/context", html)
        self.assertIn("/api/integrations/warp/launch", html)

    def test_warp_companion_status_is_local_and_does_not_expose_paths_or_credentials(self):
        response = self.client.get("/api/integrations/warp")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["license"], "AGPL-3.0-only")
        self.assertIn(payload["integration_mode"], {"optional-local-companion"})
        self.assertNotIn("path", json.dumps(payload).lower())
        self.assertNotIn("token", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
