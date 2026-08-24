import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class TerminalWorkbenchTests(unittest.TestCase):
    def test_terminal_workbench_has_blocks_history_and_safe_formatted_output(self):
        html = TestClient(backend.app).get("/").text
        for control_id in (
            "terminal-workbench",
            "terminal-block-list",
            "result-render-mode",
            "copy-latest-output",
            "bookmark-latest-output",
            "terminal-history-refresh",
        ):
            self.assertIn(f'id="{control_id}"', html)
        for symbol in (
            "function renderRouteBlocks",
            "function renderSafeMarkdown",
            "function copyLatestOutput",
            "function toggleRunBookmark",
            "Ctrl+Shift+P",
        ):
            self.assertIn(symbol, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
