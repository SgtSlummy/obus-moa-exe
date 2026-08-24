import unittest

from fastapi.testclient import TestClient

import backend.main as backend
from backend.aui import action_ids, build_manifest


class AUIContractTests(unittest.TestCase):
    def test_manifest_is_surface_bounded_and_secret_free(self):
        terminal = build_manifest("terminal")
        operator = build_manifest("operator")
        ade = build_manifest("ade")

        self.assertEqual(terminal["model"], "warp-inspired-action-accessibility")
        self.assertLess(len(terminal["actions"]), len(operator["actions"]))
        self.assertLess(len(operator["actions"]), len(ade["actions"]))
        self.assertIn("route.focus", action_ids("terminal"))
        self.assertIn("plan.deliberate", action_ids("terminal"))
        self.assertIn("view.providers", action_ids("operator"))
        self.assertIn("view.rooms", action_ids("ade"))
        self.assertNotIn("api_key", repr(ade).lower())
        self.assertNotIn("token", repr(ade).lower())

    def test_manifest_endpoint_returns_keyboard_and_accessibility_contract(self):
        response = TestClient(backend.app).get("/api/aui/manifest?surface=terminal")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["surface"], "terminal")
        self.assertEqual(payload["keyboard"]["open_palette"], "Ctrl+K")
        self.assertTrue(any(view["id"] == "route-workbench" for view in payload["views"]))
        self.assertTrue(any(action["id"] == "route.run" for action in payload["actions"]))
        self.assertTrue(any(action["id"] == "plan.deliberate" for action in payload["actions"]))

    def test_custom_key_setup_url_rejects_javascript_scheme(self):
        setup = backend.key_setup_guide({"provider": "custom", "base_url": "javascript:alert(1)"})
        self.assertNotIn("javascript:", setup["docs_url"].lower())
        self.assertTrue(setup["docs_url"].startswith("https://"))
        credential_setup = backend.key_setup_guide({"provider": "custom", "base_url": "https://user:pass@example.test/?token=secret"})
        self.assertNotIn("user:pass", credential_setup["docs_url"])
        self.assertNotIn("token=secret", credential_setup["docs_url"])

    def test_ui_exposes_aui_action_rail_and_manifest_loader(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("aui-panel", "aui-status", "aui-action-list", "aui-live"):
            self.assertIn(f'id="{control_id}"', html)
        for symbol in ("/api/aui/manifest", "loadAuiManifest", "renderAuiManifest", "auiActionHandlers", "Ctrl+R", "Ctrl+L"):
            self.assertIn(symbol, html)
        self.assertIn("Escape returns focus to the route composer", html)
        self.assertIn('id="plan-workbench"', html)
        self.assertIn('/static/aui/plan.js', html)
        self.assertIn('id="plan-auto-toggle"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
