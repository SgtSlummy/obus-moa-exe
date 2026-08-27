import unittest
from pathlib import Path


class AUIPackagingContractTests(unittest.TestCase):
    def test_pyinstaller_spec_explicitly_includes_aui_module_and_static_tree(self):
        spec = (Path(__file__).resolve().parents[1] / "OBus.spec").read_text(encoding="utf-8")
        self.assertIn('"backend.aui"', spec)
        self.assertIn('"backend.aui_events"', spec)
        self.assertIn('destination = Path("backend/static") / rp.parent', spec)
        self.assertIn("OPTIONAL_HIDDEN_IMPORTS", spec)
        self.assertIn("optional_module_available", spec)
        self.assertIn("hiddenimports.extend", spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
