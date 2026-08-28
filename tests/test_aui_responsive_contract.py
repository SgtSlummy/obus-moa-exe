import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import backend.main as backend


class AUIResponsiveContractTests(unittest.TestCase):
    def test_workbench_exposes_responsive_layout_controls(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("aui-layout", "sidebar-toggle", "density-select"):
            self.assertIn(f'id="{control_id}"', html)
        for marker in ("prefers-reduced-motion", "data-density", "/static/aui/layout.js"):
            self.assertIn(marker, html)

    def test_terminal_workbench_can_shrink_at_medium_desktop_widths(self):
        html = TestClient(backend.app).get("/").text
        # Keep the source-level guard close to the live 1024px regression check:
        # the rail collapses before the composer, stack, or blocks can force
        # a wider intrinsic grid track.
        for marker in (
            ".terminal-stack{display:grid;gap:14px;min-width:0}",
            ".terminal-block{min-width:0}",
            ".terminal-command{min-width:0}",
            "@media(max-width:1100px){.terminal-workbench{grid-template-columns:minmax(0,1fr)}",
        ):
            self.assertIn(marker, html)


    def test_scaled_desktop_windows_compact_navigation_before_controls_clip(self):
        html = TestClient(backend.app).get("/").text
        for marker in (
            "@media(max-width:1280px) and (min-width:721px)",
            ".shell{grid-template-columns:76px minmax(0,1fr);max-width:none}",
            ".top{align-items:flex-start;flex-wrap:wrap;gap:12px}",
            ".top>.actions{flex:1 1 440px;justify-content:flex-end;gap:6px}",
        ):
            self.assertIn(marker, html)


    def test_major_risk_stage_hands_off_to_runtime_approval_view(self):
        runtime_script = Path(backend.__file__).parent / "static" / "aui" / "runtime.js"
        source = runtime_script.read_text(encoding="utf-8")
        self.assertIn('if (typeof root.setPage === "function") root.setPage("runtime");', source)
        self.assertIn("Major-risk work stops here", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
