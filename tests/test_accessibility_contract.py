import unittest
from pathlib import Path


class AccessibilityContractTests(unittest.TestCase):
    def test_toggle_inputs_remain_focusable_for_keyboard_users(self):
        html = (Path(__file__).resolve().parents[1] / "backend" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn(".toggle input{display:none}", html)
        for marker in (".toggle input:focus-visible+.track", "aria-keyshortcuts", "role=\"status\"", "announceAui", "workspace-filter"):
            self.assertIn(marker, html)

    def test_toggles_use_vertical_up_down_motion(self):
        html = (Path(__file__).resolve().parents[1] / "backend" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn(".track{width:24px;height:42px", html)
        self.assertIn("transform:translateY(18px)", html)
        self.assertNotIn("transform:translateX(18px)", html)

if __name__ == "__main__":
    unittest.main()
