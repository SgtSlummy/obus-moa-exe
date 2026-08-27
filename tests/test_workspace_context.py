import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend
from backend.workspace_context import (
    WorkspaceConflictError,
    WorkspaceContextError,
    read_workspace_file,
    workspace_changes_context,
    workspace_diff_context,
    workspace_status,
    workspace_tree,
    write_workspace_file,
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
        (self.root / ".ssh" / "config").write_text("Host secret", encoding="utf-8")
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
        for path in (".aws/credentials", ".ssh/id_rsa", ".ssh/config", ".npmrc"):
            with self.assertRaises(WorkspaceContextError):
                read_workspace_file(str(self.root), path)

        with self.assertRaises(WorkspaceContextError):
            read_workspace_file(str(self.root), "../outside.txt")
        with self.assertRaises(WorkspaceContextError):
            read_workspace_file(str(self.root), str(Path(self.tempdir.name).parent / "outside.txt"))

    def test_secret_shaped_workspace_root_is_rejected(self):
        status = workspace_status(str(self.root / ".ssh"))
        self.assertFalse(status["valid"])
        with self.assertRaises(WorkspaceContextError):
            read_workspace_file(str(self.root / ".ssh"), "config")

    def test_binary_file_returns_metadata_without_content(self):
        (self.root / "image.bin").write_bytes(b"\x00\x01\x02")
        value = read_workspace_file(str(self.root), "image.bin")
        self.assertTrue(value["binary"])
        self.assertIsNone(value["content"])
        self.assertEqual(value["size"], 3)

    def test_diff_context_stays_bounded_without_git(self):
        with patch("backend.workspace_context.shutil.which", return_value=None):
            value = workspace_diff_context(str(self.root), "src/main.py")
        self.assertFalse(value["diff_available"])
        self.assertTrue(value["read_only"])
        self.assertIn("Git is not available", value["reason"])
        self.assertEqual(value["file"]["path"], "src/main.py")

    def test_diff_context_uses_non_interactive_git_flags(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            if "status" in command:
                return type("Result", (), {"returncode": 0, "stdout": b" M src/main.py\n", "stderr": b""})()
            if "cat-file" in command:
                return type("Result", (), {"returncode": 0, "stdout": b"15\n", "stderr": b""})()
            return type("Result", (), {"returncode": 0, "stdout": b"diff --git a/src/main.py b/src/main.py\n-old\n+new\n", "stderr": b""})()

        with patch("backend.workspace_context.shutil.which", return_value="C:/Git/bin/git.exe"), patch(
            "backend.workspace_context.subprocess.run", side_effect=fake_run
        ):
            value = workspace_diff_context(str(self.root), "src/main.py")

        self.assertTrue(value["diff_available"])
        self.assertTrue(value["changed"])
        self.assertIn("+new", value["diff"])
        diff_command, diff_kwargs = calls[-1]
        self.assertIn("--no-ext-diff", diff_command)
        self.assertIn("--no-textconv", diff_command)
        self.assertIn("diff.external=", diff_command)
        self.assertFalse(diff_kwargs["shell"])
        self.assertEqual(diff_kwargs["stdin"], subprocess.DEVNULL)

    def test_workspace_change_manifest_is_bounded_and_filters_secret_paths(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return type("Result", (), {
                "returncode": 0,
                "stdout": b" M src/main.py\0?? README.md\0?? .env\0D  removed.py\0R  src/renamed.py\0src/main.py\0",
                "stderr": b"",
            })()

        with patch("backend.workspace_context.shutil.which", return_value="C:/Git/bin/git.exe"), patch(
            "backend.workspace_context.subprocess.run", side_effect=fake_run
        ):
            value = workspace_changes_context(str(self.root))

        self.assertTrue(value["available"])
        self.assertTrue(value["read_only"])
        paths = {item["path"]: item for item in value["changes"]}
        self.assertEqual(paths["src/main.py"]["status"], "modified")
        self.assertEqual(paths["README.md"]["status"], "untracked")
        self.assertEqual(paths["removed.py"]["status"], "deleted")
        self.assertFalse(paths["removed.py"]["reviewable"])
        self.assertNotIn(".env", paths)
        self.assertEqual(paths["src/renamed.py"]["previous_path"], "src/main.py")
        command, kwargs = calls[0]
        self.assertIn("status", command)
        self.assertIn("--porcelain=v1", command)
        self.assertIn("-z", command)
        self.assertIn("--untracked-files=all", command)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)

    def test_safe_local_draft_write_is_atomic_and_conflict_checked(self):
        before = read_workspace_file(str(self.root), "src/main.py")
        result = write_workspace_file(
            str(self.root),
            "src/main.py",
            "print('updated')\n",
            expected_sha256=before["sha256"],
        )
        self.assertTrue(result["changed"])
        self.assertEqual((self.root / "src" / "main.py").read_text(encoding="utf-8"), "print('updated')\n")
        self.assertEqual(result["file"]["content"], "print('updated')")
        self.assertEqual(result["file"]["editor_content"], "print('updated')\n")
        with self.assertRaises(WorkspaceConflictError):
            write_workspace_file(
                str(self.root),
                "src/main.py",
                "print('stale')\n",
                expected_sha256=before["sha256"],
            )

    def test_secret_like_source_or_draft_is_not_editable(self):
        source = self.root / "src" / "settings.py"
        source.write_text("API_KEY = 'secret'\n", encoding="utf-8")
        value = read_workspace_file(str(self.root), "src/settings.py")
        self.assertFalse(value["editable"])
        self.assertIsNone(value["sha256"])
        regular = read_workspace_file(str(self.root), "src/main.py")
        with self.assertRaises(WorkspaceContextError):
            write_workspace_file(
                str(self.root),
                "src/main.py",
                "TOKEN = 'secret'\n",
                expected_sha256=regular["sha256"],
            )

    def test_api_exposes_status_tree_and_file_context(self):
        client = TestClient(backend.app)
        state_file = self.root / "state.json"
        with patch.object(backend, "STATE_FILE", state_file):
            backend.save_state(backend.normalize_state({"settings": {"workspace_root": str(self.root)}}))
            self.assertEqual(client.get("/api/workspace/status").status_code, 200)
            self.assertEqual(client.get("/api/workspace/changes").status_code, 200)
            tree = client.get("/api/workspace/tree").json()
            self.assertIn("src/main.py", {item["path"] for item in tree["entries"]})
            content = client.get("/api/workspace/file", params={"path": "src/main.py"})
            self.assertEqual(content.status_code, 200)
            self.assertIn("print", content.json()["content"])
            saved = client.put(
                "/api/workspace/file",
                json={"path": "src/main.py", "content": "print('saved')\n", "expected_sha256": content.json()["sha256"]},
            )
            self.assertEqual(saved.status_code, 200)
            self.assertTrue(saved.json()["changed"])
            major = client.put(
                "/api/workspace/file",
                json={"path": "src/main.py", "content": "format the entire disk", "expected_sha256": saved.json()["file"]["sha256"]},
            )
            self.assertEqual(major.status_code, 409)

    def test_ui_exposes_read_only_workspace_context_controls(self):
        client = TestClient(backend.app)
        html = client.get("/").text
        for control_id in ("workspace-context", "workspace-root", "workspace-tree", "workspace-file", "workspace-editor", "workspace-refresh", "workspace-review-all", "workspace-change-review", "workspace-change-summary", "workspace-change-list", "workspace-use-context", "workspace-show-diff", "workspace-edit", "workspace-save", "workspace-discard"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("loadWorkspaceContext", html)
        self.assertIn("read-only local context", html)
        workspace_js = client.get("/static/aui/workspace.js")
        self.assertEqual(workspace_js.status_code, 200)
        self.assertIn("/api/workspace/diff", workspace_js.text)
        self.assertIn("/api/workspace/changes", workspace_js.text)
        self.assertIn("showDiff", workspace_js.text)
        self.assertIn("loadWorkspaceChanges", workspace_js.text)
        self.assertIn("editDraft", workspace_js.text)
        self.assertIn("saveDraft", workspace_js.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
