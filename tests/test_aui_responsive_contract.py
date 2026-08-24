import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class AUIResponsiveContractTests(unittest.TestCase):
    def test_workbench_exposes_responsive_layout_controls(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("aui-layout", "sidebar-toggle", "density-select"):
            self.assertIn(f'id="{control_id}"', html)
        for marker in ("prefers-reduced-motion", "data-density", "/static/aui/layout.js"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
