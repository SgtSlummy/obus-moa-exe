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
            "mobile-nav-drawer",
            "mobile-control-drawer",
            "mobile-current-page",
            "rooms-workspace-splitter",
            "workspace-context-splitter",
            "studio-workspace-splitter",
            "page-subtitle",
            "agents-jump-top",
            "providers-jump-top",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn('role="separator"', html)
        self.assertIn('aria-orientation="vertical"', html)
        self.assertIn('aria-valuemin="45"', html)
        self.assertIn('aria-valuemax="75"', html)
        self.assertIn('aria-valuenow="62"', html)
        self.assertIn("const subtitles=", html)
        self.assertIn("if(name==='dashboard')", html)
        self.assertIn("subtitles.dashboard", html)
        self.assertNotIn("subtitles[name]", html)
        self.assertLess(html.index('data-page-panel="dashboard"'), html.index('id="home-status-header"'))
        self.assertLess(html.index('id="home-status-header"'), html.index('data-page-panel="workspace"'))
        for control_id in ("per-agent-context-window", "context-utilization-percent", "shared-task-context"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("per_agent_context_window:Number(e.target.value)", html)
        self.assertIn("context_utilization_percent:Number(e.target.value)", html)
        self.assertIn("shared_task_context:e.target.checked", html)
        self.assertIn("formatReceiptTimestamp", html)
        self.assertIn("syncPageJumpButtons", html)
        self.assertIn("data-page-jump-top", html)
        self.assertIn('aria-label="Read-only workspace">Workspace</button>', html)
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
            "obus-aui-split-rooms",
            "obus-aui-split-workspace",
            "obus-aui-split-studio",
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
            ".adjustable-workspace",
            "word-break: break-word",
            ".top .layout-control",
            "white-space: nowrap",
            "textarea::-webkit-scrollbar-button",
            "#rooms-workspace > :first-child",
            ".terminal-history small",
            "#settings-import-preview",
            "grid-row: 1 / 3",
            ".page-jump-top",
            '.page[data-page-panel="runs"] > .panel > .panel-body',
            "font-size: .8125rem",
            "#rooms-workspace #room-list > .empty::before",
        ):
            self.assertIn(marker, heritage.text)
        workbench_rule = heritage.text.split(".terminal-workbench {", 1)[1].split("}", 1)[0]
        self.assertIn("display: grid", workbench_rule)
        self.assertIn("minmax(0, var(--run-primary-fr))", workbench_rule)
        self.assertIn("${ratio.toFixed(4)}fr", layout.text)
        self.assertIn(".key-actions a.button", heritage.text)
        self.assertNotIn("var(--phi)fr", heritage.text)
        phone = heritage.text.split("@media (max-width: 720px)", 1)[1].split("@media", 1)[0]
        self.assertIn(".mobile-drawer-summary", phone)
        self.assertIn(".mobile-control-drawer:not([open]) > .actions", phone)
        self.assertIn(".mobile-nav-drawer:not([open]) > .nav", phone)
        self.assertNotIn("overflow-x: auto", phone)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", phone)
        self.assertIn('.page[data-page-panel="settings"] .row', phone)
        self.assertIn("#settings-import-preview", phone)
        self.assertIn("max-height: none", phone)
        self.assertIn("overflow: visible", phone)
        for forbidden in ("prompt", "output", "provider", "api_key", "bearer"):
            self.assertNotIn(f'obus-aui-{forbidden}', layout.text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
