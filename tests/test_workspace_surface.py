import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class WorkspaceSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(backend.app)

    def test_dashboard_exposes_workspace_surface_and_routing_policy(self):
        payload = self.client.get("/api/dashboard").json()
        self.assertIn(payload["settings"]["workspace_surface"], {"terminal", "operator", "ade"})
        self.assertIn(payload["settings"]["routing_policy"], {"local-first", "auto-open", "manual"})

    def test_ui_exposes_surface_selector_and_surface_aware_navigation(self):
        html = self.client.get("/").text
        for control_id in ("workspace-surface", "workspace-surface-badge", "workspace-nav"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('data-surface-min="terminal"', html)
        self.assertIn('data-surface-min="operator"', html)
        self.assertIn('data-surface-min="ade"', html)
        self.assertIn("function applyWorkspaceSurface", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
