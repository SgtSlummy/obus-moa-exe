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
        self.assertIn('/static/aui/runtime.js', html)
        self.assertIn('/static/aui/providers.js', html)
        self.assertIn('/static/aui/rooms.js', html)
        self.assertIn('/static/aui/plan.js', html)
        self.assertIn('/static/aui/memory.js', html)
        self.assertIn('legacyRuntime', html)

    def test_external_aui_modules_are_served(self):
        client = TestClient(backend.app)
        css = client.get('/static/aui/tokens.css')
        js = client.get('/static/aui/route-events.js')
        layout = client.get('/static/aui/layout.js')
        workspace = client.get('/static/aui/workspace.js')
        runtime = client.get('/static/aui/runtime.js')
        providers = client.get('/static/aui/providers.js')
        rooms = client.get('/static/aui/rooms.js')
        plan = client.get('/static/aui/plan.js')
        memory = client.get('/static/aui/memory.js')
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertEqual(layout.status_code, 200)
        self.assertEqual(workspace.status_code, 200)
        self.assertEqual(runtime.status_code, 200)
        self.assertEqual(providers.status_code, 200)
        self.assertEqual(rooms.status_code, 200)
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(memory.status_code, 200)
        self.assertIn('--aui-density-scale', css.text)
        self.assertIn('OBusRouteEvents', js.text)
        self.assertIn('OBusAuiLayout', layout.text)
        self.assertIn('OBusWorkspace', workspace.text)
        self.assertIn('OBusRuntime', runtime.text)
        self.assertIn('OBusProviders', providers.text)
        self.assertIn('OBusRooms', rooms.text)
        self.assertIn('OBusPlan', plan.text)
        self.assertIn('OBusMemory', memory.text)

    def test_heritage_workbench_loads_last_with_offline_safe_phi_tokens(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        heritage = client.get('/static/aui/heritage-workbench.css')

        self.assertIn('/static/aui/heritage-workbench.css', html)
        self.assertLess(html.index('</style>'), html.index('/static/aui/heritage-workbench.css'))
        self.assertEqual(heritage.status_code, 200)
        for marker in (
            '--phi: 1.61803398875',
            '--space-phi',
            '--ink:',
            '--parchment:',
            '--brass:',
            '--verdigris:',
            '--focus:',
            '--control-min: 40px',
            'grid-template-columns: minmax(0, var(--phi)fr) minmax(17rem, 1fr)',
            'resize: vertical',
        ):
            self.assertIn(marker, heritage.text)
        self.assertNotIn('@import url(', heritage.text)
        self.assertNotIn('https://fonts.', heritage.text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
