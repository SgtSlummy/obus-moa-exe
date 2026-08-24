import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTests(unittest.TestCase):
    def test_docs_describe_warp_inspired_workspace_contract(self):
        readme = (ROOT / "README_OBUS_EXE.md").read_text(encoding="utf-8")
        api = (ROOT / "backend" / "API_ENDPOINTS.md").read_text(encoding="utf-8")
        for text in (readme, api):
            self.assertIn("Terminal", text)
            self.assertIn("Operator", text)
            self.assertIn("ADE", text)
            self.assertIn("Auto (open)", text)
            self.assertIn("/api/settings/export", text)
            self.assertIn("/api/workspace/status", text)
            self.assertIn("/api/runs", text)

    def test_spec_includes_new_runtime_modules(self):
        spec = (ROOT / "OBus.spec").read_text(encoding="utf-8")
        self.assertIn('"backend.user_settings"', spec)
        self.assertIn('"backend.workspace_context"', spec)
        self.assertIn('"backend.run_receipts"', spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
