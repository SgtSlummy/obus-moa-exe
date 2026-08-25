import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class AUILayoutPersistenceTests(unittest.TestCase):
    def test_run_splitter_and_layout_presets_are_semantic_and_visible(self):
        html = TestClient(backend.app).get("/").text
        self.assertNotIn("repeat(3,minmax(0,1fr);", html)
        self.assertIn("repeat(3,minmax(0,1fr));", html)
        for control_id in (
            "run-workbench-splitter",
            "layout-preset-select",
            "layout-reset",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('role="separator"', html)
        self.assertIn('aria-orientation="vertical"', html)
        self.assertIn('aria-valuemin="45"', html)
        self.assertIn('aria-valuemax="75"', html)
        self.assertIn('aria-valuenow="62"', html)
        for value in ("focus", "review", "deck", "studio"):
            self.assertIn(f'value="{value}"', html)

    def test_layout_module_persists_only_bounded_visual_preferences(self):
        client = TestClient(backend.app)
        layout = client.get("/static/aui/layout.js")
        heritage = client.get("/static/aui/heritage-workbench.css")
        self.assertEqual(layout.status_code, 200)
        self.assertEqual(heritage.status_code, 200)
        for marker in (
            "bindResizablePane",
            "setPointerCapture",
            "ArrowLeft",
            "ArrowRight",
            "Home",
            "End",
            "obus-aui-split-run",
            "obus-aui-preset",
            "safeStorage.removeItem",
            "obus-layout-preset",
            "61.803398875",
            'event.key === "Home") next = MIN_SPLIT',
        ):
            self.assertIn(marker, layout.text)
        for marker in (
            "--run-primary-fr",
            "--run-secondary-fr",
            "--splitter-size",
            ".pane-splitter",
            "cursor: col-resize",
            "--splitter-size: 40px",
            ".aui-action > span",
            ".guide div",
        ):
            self.assertIn(marker, heritage.text)
        workbench_rule = heritage.text.split(".terminal-workbench {", 1)[1].split("}", 1)[0]
        self.assertIn("display: grid", workbench_rule)
        self.assertIn("minmax(0, var(--run-primary-fr))", workbench_rule)
        self.assertIn("${ratio.toFixed(4)}fr", layout.text)
        self.assertIn(".key-actions a.button", heritage.text)
        self.assertNotIn("var(--phi)fr", heritage.text)
        for forbidden in ("prompt", "output", "provider", "api_key", "bearer"):
            self.assertNotIn(f'obus-aui-{forbidden}', layout.text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
