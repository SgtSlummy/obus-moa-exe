import subprocess
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend


class AgentVisualsContractTests(unittest.TestCase):
    def test_dashboard_loads_agent_visual_layer(self):
        client = TestClient(backend.app)
        html = client.get("/").text
        self.assertIn('/static/aui/agent-visuals.css', html)
        self.assertIn('/static/aui/agent-visuals.js', html)
        self.assertIn('agent-monologue-dialog', html)
        self.assertIn('data-agent-face', html)

    def test_agent_visual_assets_are_served_and_secret_safe(self):
        client = TestClient(backend.app)
        css = client.get('/static/aui/agent-visuals.css')
        js = client.get('/static/aui/agent-visuals.js')
        runtime = client.get('/static/aui/runtime.js')
        rooms = client.get('/static/aui/rooms.js')
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertEqual(runtime.status_code, 200)
        self.assertEqual(rooms.status_code, 200)
        self.assertIn('--phi', css.text)
        self.assertIn('agent-think-breathe', css.text)
        self.assertIn('inner monologue', js.text.lower())
        self.assertIn('persistentMarkup', runtime.text)
        self.assertIn('OBusAgentVisuals', rooms.text)
        self.assertNotIn('api_key', js.text.lower())
        self.assertNotIn('bearer ', js.text.lower())

    def test_agent_visual_javascript_parses(self):
        path = Path(__file__).resolve().parents[1] / 'backend' / 'static' / 'aui' / 'agent-visuals.js'
        result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_compact_shuffle_decks_keep_key_copy_below_the_art(self):
        client = TestClient(backend.app)
        html = client.get('/').text
        css = client.get('/static/aui/deck-workspace.css')
        providers = client.get('/static/aui/providers.js').text

        self.assertIn('/static/aui/deck-workspace.css', html)
        self.assertEqual(css.status_code, 200)
        self.assertIn('class="key-grid shuffle-deck key-shuffle-deck"', html)
        self.assertIn('class="grid shuffle-deck tarot-shuffle-deck"', html)
        self.assertIn('--tarot-art-scale: .75', css.text)
        self.assertIn('--key-art-scale: .75', css.text)
        self.assertIn('grid-template-areas: "art" "meta" "actions"', css.text)
        self.assertIn('@keyframes card-shuffle-deal', css.text)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css.text)
        self.assertIn('map((provider, index)', providers)
        self.assertIn('class="key-card selectable shuffle-card"', providers)
        self.assertIn('class="key-figure"', providers)
        self.assertLess(providers.index('class="key-figure"'), providers.index('class="key-meta"'))


if __name__ == '__main__':
    unittest.main()
