import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class CommandPaletteTests(unittest.TestCase):
    def test_command_palette_contract_is_present_in_the_ui(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("command-palette", "command-palette-input", "command-palette-results"):
            self.assertIn(f'id="{control_id}"', html)
        for symbol in ("openCommandPalette", "runCommandPaletteAction", "Ctrl+K", "Escape"):
            self.assertIn(symbol, html)
        for action in ("Route task", "Refresh live state", "Warm GPU", "Settings", "Memory", "Cards & Keys", "Rooms", "Export latest receipt"):
            self.assertIn(action, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
