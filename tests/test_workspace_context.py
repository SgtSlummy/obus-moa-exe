import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend
from backend.workspace_context import (
    WorkspaceContextError,
    read_workspace_file,
    workspace_status,
    workspace_tree,
)


class WorkspaceContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
        (self.root / "README.md").write_text("# workspace\n", encoding="utf-8")
        (self.root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
        (self.root / "private.pem").write_text("-----BEGIN PRIVATE KEY-----\nsecret\n", encoding="utf-8")
        (self.root / ".aws").mkdir()
        (self.root / ".aws" / "credentials").write_text("aws_secret", encoding="utf-8")
        (self.root / ".ssh").mkdir()
        (self.root / ".ssh" / "id_rsa").write_text("private", encoding="utf-8")
        (self.root / ".npmrc").write_text("//registry.npmjs.org/:_authToken=secret", encoding="utf-8")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_workspace_status_is_local_and_secret_safe(self):
        status = workspace_status(str(self.root))
        self.assertTrue(status["configured"])
        self.assertTrue(status["valid"])
        self.assertEqual(status["root"], str(self.root.resolve()))
        self.assertNotIn("API_KEY", json.dumps(status))

    def test_tree_is_bounded_and_omits_secret_files(self):
        tree = workspace_tree(str(self.root), max_files=10, max_depth=3)
        paths = {item["path"] for item in tree["entries"]}
        self.assertIn("README.md", paths)
        self.assertIn("src/main.py", paths)
        self.assertNotIn(".env", paths)
        self.assertNotIn("private.pem", paths)
        self.assertNotIn(".aws", paths)
        self.assertNotIn(".ssh", paths)
        self.assertNotIn(".npmrc", paths)
        self.assertLessEqual(len(tree["entries"]), 10)

    def test_credential_files_are_rejected_from_direct_reads(self):
        for path in (".aws/credentials", ".ssh/id_rsa", ".npmrc"):
            with self.assertRaises(WorkspaceContextError):
                read_workspace_file(str(self.root), path)

        with self.assertRaises(WorkspaceContextError):
            read_workspace_file(str(self.root), "../outside.txt")
        with self.assertRaises(WorkspaceContextError):
            read_workspace_file(str(self.root), str(Path(self.tempdir.name).parent / "outside.txt"))

    def test_binary_file_returns_metadata_without_content(self):
        (self.root / "image.bin").write_bytes(b"\x00\x01\x02")
        value = read_workspace_file(str(self.root), "image.bin")
        self.assertTrue(value["binary"])
        self.assertIsNone(value["content"])
        self.assertEqual(value["size"], 3)

    def test_api_exposes_status_tree_and_file_context(self):
        client = TestClient(backend.app)
        state_file = self.root / "state.json"
        with patch.object(backend, "STATE_FILE", state_file):
            backend.save_state(backend.normalize_state({"settings": {"workspace_root": str(self.root)}}))
            self.assertEqual(client.get("/api/workspace/status").status_code, 200)
            tree = client.get("/api/workspace/tree").json()
            self.assertIn("src/main.py", {item["path"] for item in tree["entries"]})
            content = client.get("/api/workspace/file", params={"path": "src/main.py"})
            self.assertEqual(content.status_code, 200)
            self.assertIn("print", content.json()["content"])

    def test_ui_exposes_read_only_workspace_context_controls(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("workspace-context", "workspace-root", "workspace-tree", "workspace-file", "workspace-refresh", "workspace-use-context"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("loadWorkspaceContext", html)
        self.assertIn("read-only local context", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
