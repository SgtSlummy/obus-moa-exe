"""Durable workspace checkpoints, rollback receipts, and failure circuit breakers."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import time
import uuid
from pathlib import Path
from typing import Any

from backend.secret_safety import redact_text
from backend.workspace_context import _is_secret_name

EXCLUDED_DIRS = {".git", ".venv", ".venv-build", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}
MAX_CHANGE_FILES = 100
MAX_CHANGE_SCAN_FILES = 1000
MAX_CHANGE_FILE_BYTES = 128 * 1024
MAX_CHANGE_DIFF_BYTES = 192 * 1024


class RecoveryManager:
    """Best-effort transactional protection around autonomous workspace execution."""

    def __init__(self, database: Path, max_file_bytes: int = 10 * 1024 * 1024,
                 max_checkpoint_bytes: int = 100 * 1024 * 1024):
        self.database = database.resolve()
        self.root = self.database.parent / "checkpoints"
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes
        self.max_checkpoint_bytes = max_checkpoint_bytes
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS harness_checkpoints (
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL, workspace TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL, manifest TEXT NOT NULL, status TEXT NOT NULL,
                    bytes_copied INTEGER NOT NULL, files_copied INTEGER NOT NULL,
                    created_at REAL NOT NULL, completed_at REAL, receipt TEXT
                );
                CREATE TABLE IF NOT EXISTS harness_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, error_type TEXT NOT NULL, error_message TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_harness_failure_fingerprint
                    ON harness_failures(fingerprint, occurred_at);
            """)

    def _excluded(self, path: Path) -> bool:
        resolved = path.resolve()
        database_files = {self.database, Path(str(self.database) + "-wal"), Path(str(self.database) + "-shm")}
        if resolved in database_files or resolved == self.root or self.root in resolved.parents:
            return True
        return any(part in EXCLUDED_DIRS for part in path.parts)

    def _workspace_files(self, workspace: Path) -> list[Path]:
        files: list[Path] = []
        for current, directories, names in os.walk(workspace, followlinks=False):
            current_path = Path(current)
            directories[:] = [name for name in directories if name not in EXCLUDED_DIRS
                               and not self._excluded(current_path / name)]
            for name in names:
                path = current_path / name
                if self._excluded(path) or path.is_symlink() or not path.is_file():
                    continue
                files.append(path)
        return files

    def _bounded_workspace_files(self, workspace: Path, limit: int = MAX_CHANGE_SCAN_FILES) -> tuple[list[Path], bool]:
        """Collect a finite discovery slice for change review without a full project walk."""

        files: list[Path] = []
        cap = max(1, min(int(limit), MAX_CHANGE_SCAN_FILES))
        for current, directories, names in os.walk(workspace, followlinks=False):
            current_path = Path(current)
            directories[:] = [name for name in directories if name not in EXCLUDED_DIRS
                               and not self._excluded(current_path / name)]
            for name in names:
                path = current_path / name
                if self._excluded(path) or path.is_symlink() or not path.is_file():
                    continue
                if len(files) >= cap:
                    return files, True
                files.append(path)
        return files, False

    @staticmethod
    def _metadata(path: Path) -> dict[str, Any]:
        info = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"size": info.st_size, "mode": stat.S_IMODE(info.st_mode), "sha256": digest.hexdigest()}

    def create(self, task_id: str, workspace: Path) -> dict[str, Any]:
        workspace = workspace.resolve()
        checkpoint_id = uuid.uuid4().hex
        snapshot = self.root / checkpoint_id
        snapshot.mkdir(parents=True)
        manifest: dict[str, dict[str, Any]] = {}
        copied = 0
        skipped = 0
        for path in self._workspace_files(workspace):
            relative = path.relative_to(workspace)
            metadata = self._metadata(path)
            if metadata["size"] > self.max_file_bytes or copied + metadata["size"] > self.max_checkpoint_bytes:
                metadata["snapshot"] = False
                skipped += 1
            else:
                destination = snapshot / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
                metadata["snapshot"] = True
                copied += metadata["size"]
            manifest[relative.as_posix()] = metadata
        record = {"id": checkpoint_id, "task_id": task_id, "workspace": str(workspace),
                  "snapshot_path": str(snapshot), "manifest": manifest, "status": "ready",
                  "bytes_copied": copied, "files_copied": sum(1 for item in manifest.values() if item["snapshot"]),
                  "files_skipped": skipped, "created_at": time.time()}
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_checkpoints(id,task_id,workspace,snapshot_path,manifest,status,bytes_copied,"
                "files_copied,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (checkpoint_id, task_id, str(workspace), str(snapshot), json.dumps(manifest), "ready", copied,
                 record["files_copied"], record["created_at"]),
            )
        return record

    def get(self, checkpoint_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
        if row is None:
            raise KeyError(checkpoint_id)
        result = dict(row)
        result["manifest"] = json.loads(result["manifest"])
        result["receipt"] = json.loads(result["receipt"]) if result["receipt"] else None
        return result

    def list(self, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if task_id:
                rows = connection.execute(
                    "SELECT * FROM harness_checkpoints WHERE task_id=? ORDER BY created_at DESC LIMIT ?",
                    (task_id, max(1, min(limit, 500))),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM harness_checkpoints ORDER BY created_at DESC LIMIT ?",
                    (max(1, min(limit, 500)),),
                ).fetchall()
        return [self.get(row["id"]) for row in rows]

    @staticmethod
    def _safe_relative(workspace: Path, value: str) -> str | None:
        relative = Path(str(value or "").replace("\\", "/"))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            return None
        if any(_is_secret_name(part) for part in relative.parts):
            return None
        candidate = (workspace / relative).resolve(strict=False)
        if candidate != workspace and workspace not in candidate.parents:
            return None
        return relative.as_posix()

    @staticmethod
    def _safe_text(data: bytes) -> str | None:
        if len(data) > MAX_CHANGE_FILE_BYTES or b"\x00" in data:
            return None
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if redact_text(text, limit=max(MAX_CHANGE_FILE_BYTES, len(text) + 1)) != text.strip():
            return None
        return text

    def _current_path(self, workspace: Path, relative: str) -> Path | None:
        candidate = workspace / relative
        try:
            if not candidate.exists() or candidate.is_symlink() or not candidate.is_file():
                return None
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None
        if resolved != workspace and workspace not in resolved.parents:
            return None
        return resolved

    def _change_item(self, workspace: Path, relative: str, before: dict[str, Any] | None,
                     current: Path | None) -> dict[str, Any] | None:
        if before is None and current is None:
            return None
        if before is None:
            size = current.stat().st_size if current else 0
            return {
                "path": relative, "status": "added", "before_size": None, "after_size": size,
                "diff_available": size <= MAX_CHANGE_FILE_BYTES,
                "reason": None if size <= MAX_CHANGE_FILE_BYTES else "New file exceeds the bounded diff limit.",
            }
        if current is None:
            return {
                "path": relative, "status": "deleted", "before_size": int(before.get("size") or 0), "after_size": None,
                "diff_available": bool(before.get("snapshot")) and int(before.get("size") or 0) <= MAX_CHANGE_FILE_BYTES,
                "reason": None if before.get("snapshot") and int(before.get("size") or 0) <= MAX_CHANGE_FILE_BYTES else "The checkpoint cannot provide a bounded text baseline.",
            }
        size = current.stat().st_size
        if size > MAX_CHANGE_FILE_BYTES or int(before.get("size") or 0) > MAX_CHANGE_FILE_BYTES:
            return {
                "path": relative, "status": "unreviewable", "before_size": int(before.get("size") or 0), "after_size": size,
                "diff_available": False, "reason": "File exceeds the bounded change-review limit.",
            }
        try:
            after = self._metadata(current)
        except OSError:
            return {
                "path": relative, "status": "unreviewable", "before_size": int(before.get("size") or 0), "after_size": size,
                "diff_available": False, "reason": "Current file could not be safely inspected.",
            }
        if after["sha256"] == before.get("sha256"):
            return None
        return {
            "path": relative, "status": "modified", "before_size": int(before.get("size") or 0), "after_size": size,
            "diff_available": bool(before.get("snapshot")),
            "reason": None if before.get("snapshot") else "The checkpoint did not retain a text baseline for this file.",
        }

    def task_changes(self, task_id: str, limit: int = MAX_CHANGE_FILES) -> dict[str, Any]:
        """Return a bounded, read-only manifest of changes since a task's latest checkpoint."""

        checkpoints = self.list(task_id, limit=1)
        if not checkpoints:
            raise KeyError(task_id)
        checkpoint = checkpoints[0]
        workspace = Path(checkpoint["workspace"]).resolve()
        if not workspace.is_dir():
            return {
                "task_id": task_id, "checkpoint": self._checkpoint_public(checkpoint), "changes": [],
                "counts": {}, "truncated": False, "read_only": True,
                "reason": "The task workspace is no longer available for review.",
            }
        max_items = max(1, min(int(limit), MAX_CHANGE_FILES))
        baseline = {
            relative: metadata for raw_relative, metadata in checkpoint["manifest"].items()
            if (relative := self._safe_relative(workspace, raw_relative)) is not None
        }
        changes: list[dict[str, Any]] = []
        truncated = False
        baseline_checked = 0
        for relative, metadata in baseline.items():
            if baseline_checked >= MAX_CHANGE_SCAN_FILES or len(changes) >= max_items:
                truncated = True
                break
            baseline_checked += 1
            item = self._change_item(workspace, relative, metadata, self._current_path(workspace, relative))
            if item is not None:
                changes.append(item)
        current_files, discovery_truncated = self._bounded_workspace_files(workspace)
        truncated = truncated or discovery_truncated
        for path in current_files:
            try:
                relative = self._safe_relative(workspace, path.relative_to(workspace).as_posix())
            except ValueError:
                continue
            if relative is None or relative in baseline:
                continue
            item = self._change_item(workspace, relative, None, path)
            if item is not None:
                changes.append(item)
                if len(changes) >= max_items:
                    truncated = True
                    break
        changes.sort(key=lambda item: (item["status"], item["path"]))
        if len(changes) > max_items:
            changes = changes[:max_items]
            truncated = True
        counts: dict[str, int] = {}
        for item in changes:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {
            "task_id": task_id, "checkpoint": self._checkpoint_public(checkpoint), "changes": changes,
            "counts": counts, "truncated": truncated, "read_only": True,
            "reason": None if changes else "No safe, bounded workspace changes were found since this checkpoint.",
        }

    @staticmethod
    def _checkpoint_public(checkpoint: dict[str, Any]) -> dict[str, Any]:
        skipped = checkpoint.get("files_skipped")
        if skipped is None:
            skipped = sum(1 for metadata in checkpoint.get("manifest", {}).values() if not metadata.get("snapshot"))
        return {
            "id": checkpoint["id"], "status": checkpoint["status"], "created_at": checkpoint["created_at"],
            "completed_at": checkpoint.get("completed_at"), "files_copied": checkpoint["files_copied"],
            "files_skipped": skipped, "bytes_copied": checkpoint["bytes_copied"],
        }

    def task_change_diff(self, task_id: str, relative_path: str) -> dict[str, Any]:
        """Return one selected, redacted unified diff without touching the workspace."""

        summary = self.task_changes(task_id)
        change = next((item for item in summary["changes"] if item["path"] == relative_path), None)
        if change is None:
            raise ValueError("Selected file is not available in this task's bounded change manifest")
        if not change["diff_available"]:
            return {"path": relative_path, "status": change["status"], "diff_available": False,
                    "truncated": False, "diff": None, "reason": change.get("reason") or "No safe text diff is available."}
        checkpoint = self.get(summary["checkpoint"]["id"])
        workspace = Path(checkpoint["workspace"]).resolve()
        snapshot = Path(checkpoint["snapshot_path"]).resolve()
        if snapshot.parent != self.root.resolve():
            raise RuntimeError("checkpoint snapshot escaped the recovery root")
        baseline = snapshot / relative_path
        current = self._current_path(workspace, relative_path)
        try:
            before = self._safe_text(baseline.read_bytes()) if baseline.is_file() else ""
            after = self._safe_text(current.read_bytes()) if current else ""
        except OSError:
            before = after = None
        if before is None or after is None:
            return {"path": relative_path, "status": change["status"], "diff_available": False,
                    "truncated": False, "diff": None, "reason": "File content is binary, secret-like, or exceeds the bounded review limit."}
        diff = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile=f"before/{relative_path}", tofile=f"after/{relative_path}", lineterm="\n",
        ))
        truncated = len(diff.encode("utf-8", errors="replace")) > MAX_CHANGE_DIFF_BYTES
        return {"path": relative_path, "status": change["status"], "diff_available": True,
                "truncated": truncated, "diff": redact_text(diff, MAX_CHANGE_DIFF_BYTES),
                "reason": "Diff truncated to the bounded review limit." if truncated else None}

    def verify_workspace(self, checkpoint_id: str) -> dict[str, Any]:
        """Check only this checkpoint's bounded text diffs before committing it.

        The validation is independent of the agent's claim of success and does
        not depend on a repository being clean or even using Git. It deliberately
        excludes secret-like, binary, and oversized files, which remain available
        to the existing change-review manifest but are never read into this check.
        """

        checkpoint = self.get(checkpoint_id)
        receipt: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "kind": "checkpoint-diff-check",
            "read_only": True,
            "status": "passed",
            "checks": [],
        }
        try:
            changes = self.task_changes(checkpoint["task_id"])["changes"]
            workspace = Path(checkpoint["workspace"]).resolve()
            snapshot = Path(checkpoint["snapshot_path"]).resolve()
            if snapshot.parent != self.root.resolve():
                raise RuntimeError("checkpoint snapshot escaped the recovery root")
            for change in changes:
                path = str(change["path"])
                if not change.get("diff_available"):
                    receipt["checks"].append({"path": path, "passed": True, "skipped": True,
                                              "reason": change.get("reason") or "No safe text diff is available."})
                    continue
                relative = self._safe_relative(workspace, path)
                current = self._current_path(workspace, relative) if relative else None
                baseline = snapshot / relative if relative else None
                try:
                    before = self._safe_text(baseline.read_bytes()) if baseline and baseline.is_file() else ""
                    after = self._safe_text(current.read_bytes()) if current else ""
                except OSError:
                    before = after = None
                if before is None or after is None:
                    receipt["checks"].append({"path": path, "passed": True, "skipped": True,
                                              "reason": "No safe text diff is available."})
                    continue
                trailing = sum(
                    1 for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="")
                    if line.startswith("+") and not line.startswith("+++") and line[1:].rstrip(" \t") != line[1:]
                )
                receipt["checks"].append({"path": path, "passed": trailing == 0,
                                          "trailing_whitespace_lines": trailing})
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            receipt["status"] = "skipped"
            receipt["reason"] = f"Checkpoint diff verification was unavailable: {type(exc).__name__}"
            return receipt

        failures = [check for check in receipt["checks"] if not check["passed"]]
        receipt["status"] = "failed" if failures else "passed"
        if failures:
            receipt["reason"] = "Checkpoint diff contains trailing whitespace introduced by this task."
        return receipt

    def complete(self, checkpoint_id: str) -> dict[str, Any]:
        receipt = {"checkpoint_id": checkpoint_id, "disposition": "committed", "completed_at": time.time()}
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE harness_checkpoints SET status='committed',completed_at=?,receipt=? WHERE id=?",
                (receipt["completed_at"], json.dumps(receipt), checkpoint_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(checkpoint_id)
        return receipt

    def rollback(self, checkpoint_id: str) -> dict[str, Any]:
        checkpoint = self.get(checkpoint_id)
        if checkpoint["status"] not in {"ready", "rollback_failed"}:
            return checkpoint["receipt"] or {"checkpoint_id": checkpoint_id, "disposition": checkpoint["status"]}
        workspace = Path(checkpoint["workspace"]).resolve()
        snapshot = Path(checkpoint["snapshot_path"]).resolve()
        if snapshot.parent != self.root.resolve() or not snapshot.is_dir():
            raise RuntimeError("checkpoint snapshot escaped the recovery root")
        restored: list[str] = []
        removed: list[str] = []
        errors: list[dict[str, str]] = []
        manifest: dict[str, dict[str, Any]] = checkpoint["manifest"]
        current = {path.relative_to(workspace).as_posix(): path for path in self._workspace_files(workspace)}
        for relative, metadata in manifest.items():
            if not metadata.get("snapshot"):
                continue
            source = (snapshot / relative).resolve()
            destination = (workspace / relative).resolve()
            if workspace != destination and workspace not in destination.parents:
                errors.append({"path": relative, "error": "destination escaped workspace"})
                continue
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                restored.append(relative)
            except OSError as exc:
                errors.append({"path": relative, "error": str(exc)})
        for relative, path in current.items():
            if relative in manifest or self._excluded(path):
                continue
            try:
                path.unlink()
                removed.append(relative)
            except OSError as exc:
                errors.append({"path": relative, "error": str(exc)})
        disposition = "rolled_back" if not errors else "rollback_failed"
        receipt = {"checkpoint_id": checkpoint_id, "disposition": disposition, "restored": restored,
                   "removed": removed, "errors": errors, "completed_at": time.time()}
        with self._connection() as connection:
            connection.execute(
                "UPDATE harness_checkpoints SET status=?,completed_at=?,receipt=? WHERE id=?",
                (disposition, receipt["completed_at"], json.dumps(receipt), checkpoint_id),
            )
        return receipt

    @staticmethod
    def fingerprint(error: BaseException) -> str:
        normalized = f"{type(error).__name__}:{str(error).strip().lower()}"
        return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()

    def record_failure(self, task_id: str, error: BaseException) -> dict[str, Any]:
        fingerprint = self.fingerprint(error)
        now = time.time()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_failures(task_id,fingerprint,error_type,error_message,occurred_at) VALUES(?,?,?,?,?)",
                (task_id, fingerprint, type(error).__name__, str(error)[-4000:], now),
            )
            count = connection.execute(
                "SELECT COUNT(*) FROM harness_failures WHERE fingerprint=? AND occurred_at>=?",
                (fingerprint, now - 900),
            ).fetchone()[0]
        return {"fingerprint": fingerprint, "count_15m": count, "circuit_open": count >= 3}

    def circuit_open(self, fingerprint: str) -> bool:
        with self._connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM harness_failures WHERE fingerprint=? AND occurred_at>=?",
                (fingerprint, time.time() - 900),
            ).fetchone()[0]
        return count >= 3
