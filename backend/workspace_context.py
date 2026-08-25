"""Bounded, read-only local workspace inspection for the OBus UI."""
from __future__ import annotations

import fnmatch
import os
import re
import stat
from pathlib import Path
from typing import Any

from backend.secret_safety import redact_text

MAX_FILES = 200
MAX_DEPTH = 6
MAX_FILE_BYTES = 64 * 1024
MAX_TEXT_LINES = 800
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "credentials.json",
    "auth.json",
    "token.json",
    "*.secret",
    ".aws",
    ".ssh",
    ".gnupg",
    ".config",
    ".npmrc",
    ".netrc",
    ".pypirc",
    "credentials",
    "credentials.*",
    "*credentials*",
    ".git",
    ".hg",
    ".svn",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
)


class WorkspaceContextError(ValueError):
    """Raised when a workspace request is invalid or outside the configured root."""


def _is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(fnmatch.fnmatch(lowered, pattern) for pattern in SECRET_PATTERNS)


def _resolved_root(root: str | os.PathLike[str] | None) -> Path:
    if not root or not str(root).strip():
        raise WorkspaceContextError("workspace root is not configured")
    candidate = Path(root).expanduser().resolve(strict=True)
    if any(_is_secret_name(part) for part in candidate.parts):
        raise WorkspaceContextError("workspace root contains a secret-shaped path component")
    if not candidate.is_dir():
        raise WorkspaceContextError("workspace root must be a directory")
    return candidate


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_path(root: Path, relative_path: str | None, *, must_exist: bool = True) -> Path:
    value = str(relative_path or "").replace("\\", "/")
    if "\x00" in value:
        raise WorkspaceContextError("path contains invalid characters")
    if not value or value == ".":
        candidate = root
    else:
        requested = Path(value)
        if requested.is_absolute() or ".." in requested.parts:
            raise WorkspaceContextError("path must stay inside the configured workspace root")
        if any(_is_secret_name(part) for part in requested.parts):
            raise WorkspaceContextError("secret-shaped workspace paths are redacted")
        candidate = (root / requested).resolve(strict=False)
    if not _inside(root, candidate):
        raise WorkspaceContextError("path resolves outside the configured workspace root")
    resolved_relative = candidate.relative_to(root)
    if any(_is_secret_name(part) for part in resolved_relative.parts):
        raise WorkspaceContextError("secret-shaped workspace paths are redacted")
    if must_exist and not candidate.exists():
        raise WorkspaceContextError("workspace path does not exist")
    return candidate


def workspace_status(root: str | os.PathLike[str] | None) -> dict[str, Any]:
    if not root or not str(root).strip():
        return {"configured": False, "valid": False, "root": None, "reason": "No workspace root configured."}
    try:
        resolved = _resolved_root(root)
    except (OSError, RuntimeError, WorkspaceContextError) as exc:
        return {"configured": True, "valid": False, "root": str(root), "reason": str(exc)}
    return {
        "configured": True,
        "valid": True,
        "root": str(resolved),
        "read_only": True,
        "limits": {"max_files": MAX_FILES, "max_depth": MAX_DEPTH, "max_file_bytes": MAX_FILE_BYTES},
    }


def workspace_tree(
    root: str | os.PathLike[str] | None,
    relative_path: str | None = None,
    *,
    max_files: int = MAX_FILES,
    max_depth: int = MAX_DEPTH,
) -> dict[str, Any]:
    resolved_root = _resolved_root(root)
    base = _safe_path(resolved_root, relative_path)
    if not base.is_dir():
        raise WorkspaceContextError("tree path must be a directory")
    max_files = min(max(int(max_files), 1), MAX_FILES)
    max_depth = min(max(int(max_depth), 1), MAX_DEPTH)
    entries: list[dict[str, Any]] = []
    skipped = 0
    for current_root, directories, files in os.walk(base, topdown=True, followlinks=False):
        current = Path(current_root)
        depth = len(current.relative_to(resolved_root).parts)
        directories[:] = sorted(directories)
        files = sorted(files)
        secret_directories = [name for name in directories if _is_secret_name(name)]
        skipped += len(secret_directories)
        directories[:] = [name for name in directories if name not in secret_directories]
        if depth >= max_depth:
            skipped += len(directories) + len(files)
            directories[:] = []
            continue
        if len(entries) >= max_files:
            skipped += len(directories) + len(files)
            directories[:] = []
            break
        for name in directories + files:
            path = current / name
            relative = path.relative_to(resolved_root).as_posix()
            if _is_secret_name(name):
                skipped += 1
                continue
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                skipped += 1
                continue
            if not _inside(resolved_root, resolved):
                skipped += 1
                continue
            if len(entries) >= max_files:
                skipped += 1
                continue
            is_directory = path.is_dir()
            item: dict[str, Any] = {"path": relative, "kind": "directory" if is_directory else "file"}
            if not is_directory:
                try:
                    item["size"] = path.stat().st_size
                except OSError:
                    item["size"] = 0
            entries.append(item)
    return {
        "root": str(resolved_root),
        "path": base.relative_to(resolved_root).as_posix() if base != resolved_root else ".",
        "entries": entries,
        "truncated": bool(skipped),
        "skipped": skipped,
        "read_only": True,
    }


def read_workspace_file(root: str | os.PathLike[str] | None, relative_path: str, *, max_bytes: int = MAX_FILE_BYTES) -> dict[str, Any]:
    resolved_root = _resolved_root(root)
    path = _safe_path(resolved_root, relative_path)
    if path.is_dir():
        raise WorkspaceContextError("workspace path is a directory")
    if _is_secret_name(path.name):
        raise WorkspaceContextError("secret-shaped workspace files are redacted")
    try:
        resolved_file = path.resolve(strict=True)
        if not _inside(resolved_root, resolved_file) or not stat.S_ISREG(resolved_file.stat().st_mode):
            raise WorkspaceContextError("workspace path is not a regular file")
    except OSError as exc:
        raise WorkspaceContextError("workspace file could not be inspected") from exc
    max_bytes = min(max(int(max_bytes), 1), MAX_FILE_BYTES)
    try:
        resolved_file = path.resolve(strict=True)
        if not _inside(resolved_root, resolved_file):
            raise WorkspaceContextError("workspace path escaped the configured root")
        size = resolved_file.stat().st_size
        with resolved_file.open("rb") as handle:
            sample = handle.read(max_bytes + 1)
    except (OSError, ValueError) as exc:
        raise WorkspaceContextError("workspace file could not be read") from exc
    truncated = len(sample) > max_bytes or size > max_bytes
    sample = sample[:max_bytes]
    result: dict[str, Any] = {
        "path": path.relative_to(resolved_root).as_posix(),
        "size": size,
        "truncated": truncated,
        "binary": False,
        "content": None,
    }
    if b"\x00" in sample:
        result["binary"] = True
        return result
    try:
        text = redact_text(sample.decode("utf-8"))
    except UnicodeDecodeError:
        result["binary"] = True
        return result
    lines = text.splitlines()
    if len(lines) > MAX_TEXT_LINES:
        text = "\n".join(lines[:MAX_TEXT_LINES])
        result["truncated"] = True
    result["content"] = text
    result["lines"] = min(len(lines), MAX_TEXT_LINES)
    return result


def workspace_diff_context(root: str | os.PathLike[str] | None, relative_path: str) -> dict[str, Any]:
    """Return bounded file context without invoking Git or a shell command."""
    return {
        "path": relative_path,
        "diff_available": False,
        "reason": "No VCS command is enabled in the local workspace context service.",
        "file": read_workspace_file(root, relative_path),
        "read_only": True,
    }
