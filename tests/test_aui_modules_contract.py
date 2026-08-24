import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend


class AUIModuleContractTests(unittest.TestCase):
    def test_html_loads_external_aui_modules(self):
        html = TestClient(backend.app).get("/").text
        self.assertIn('/static/aui/tokens.css', html)
        self.assertIn('/static/aui/route-events.js', html)
        self.assertIn('/static/aui/layout.js', html)
        self.assertIn('/static/aui/workspace.js', html)

    def test_external_aui_modules_are_served(self):
        client = TestClient(backend.app)
        css = client.get('/static/aui/tokens.css')
        js = client.get('/static/aui/route-events.js')
        layout = client.get('/static/aui/layout.js')
        workspace = client.get('/static/aui/workspace.js')
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertEqual(layout.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertIn('--aui-density-scale', css.text)
        self.assertIn('OBusRouteEvents', js.text)
        self.assertIn('OBusAuiLayout', layout.text)
        self.assertIn('OBusWorkspace', workspace.text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
