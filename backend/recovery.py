"""Durable workspace checkpoints, rollback receipts, and failure circuit breakers."""

from __future__ import annotations

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

EXCLUDED_DIRS = {".git", ".venv", ".venv-build", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}


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
