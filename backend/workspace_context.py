"""Bounded, read-only local workspace inspection for the OBus UI."""
from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from backend.secret_safety import redact_text

MAX_FILES = 200
MAX_DEPTH = 6
MAX_FILE_BYTES = 64 * 1024
MAX_TEXT_LINES = 800
MAX_DIFF_FILE_BYTES = 128 * 1024
MAX_DIFF_BYTES = 192 * 1024
MAX_WORKSPACE_CHANGES = 100
MAX_WORKSPACE_STATUS_BYTES = 256 * 1024
GIT_READ_TIMEOUT_SECONDS = 4
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
SENSITIVE_ENV = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|COOKIE|AUTHORIZATION|CREDENTIAL)",
    re.IGNORECASE,
)


class WorkspaceContextError(ValueError):
    """Raised when a workspace request is invalid or outside the configured root."""


class WorkspaceConflictError(WorkspaceContextError):
    """Raised when a local draft no longer matches the on-disk file."""


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
        "sha256": None,
        "editable": False,
        "editor_content": None,
    }
    if b"\x00" in sample:
        result["binary"] = True
        return result
    try:
        raw_text = sample.decode("utf-8")
    except UnicodeDecodeError:
        result["binary"] = True
        return result
    text = redact_text(raw_text, limit=max(MAX_FILE_BYTES, len(raw_text) + 1))
    lines = text.splitlines()
    if len(lines) > MAX_TEXT_LINES:
        text = "\n".join(lines[:MAX_TEXT_LINES])
        result["truncated"] = True
    result["content"] = text
    result["lines"] = min(len(lines), MAX_TEXT_LINES)
    if not result["truncated"] and text == raw_text.strip():
        result["sha256"] = hashlib.sha256(sample).hexdigest()
        result["editable"] = True
        result["editor_content"] = raw_text
    return result


def write_workspace_file(
    root: str | os.PathLike[str] | None,
    relative_path: str,
    content: str,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    """Atomically save one explicit, bounded, non-secret local text draft."""
    resolved_root = _resolved_root(root)
    path = _safe_path(resolved_root, relative_path)
    if path.is_dir() or _is_secret_name(path.name):
        raise WorkspaceContextError("workspace path is not an editable text file")
    try:
        resolved_file = path.resolve(strict=True)
        if not _inside(resolved_root, resolved_file) or not stat.S_ISREG(resolved_file.stat().st_mode):
            raise WorkspaceContextError("workspace path is not a regular file")
        if resolved_file.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceContextError("workspace file exceeds the editable size limit")
        original = resolved_file.read_bytes()
    except (OSError, ValueError) as exc:
        raise WorkspaceContextError("workspace file could not be prepared for editing") from exc
    actual_sha256 = hashlib.sha256(original).hexdigest()
    if not expected_sha256 or expected_sha256 != actual_sha256:
        raise WorkspaceConflictError("file changed on disk; refresh it before saving the draft")
    try:
        original_text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkspaceContextError("binary files cannot be edited in the local draft editor") from exc
    if redact_text(original_text, limit=max(MAX_FILE_BYTES, len(original_text) + 1)) != original_text.strip():
        raise WorkspaceContextError("files containing secret-like values cannot be edited in the local draft editor")
    updated_text = str(content)
    updated = updated_text.encode("utf-8")
    if len(updated) > MAX_FILE_BYTES:
        raise WorkspaceContextError("draft exceeds the editable size limit")
    if "\x00" in updated_text or redact_text(updated_text, limit=max(MAX_FILE_BYTES, len(updated_text) + 1)) != updated_text.strip():
        raise WorkspaceContextError("draft contains invalid or secret-like content")
    changed = updated != original
    if changed:
        temp_path: str | None = None
        try:
            descriptor, temp_path = tempfile.mkstemp(prefix=f".{resolved_file.name}.obus-", suffix=".tmp", dir=str(resolved_file.parent))
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, resolved_file)
            temp_path = None
        except OSError as exc:
            raise WorkspaceContextError("workspace draft could not be saved") from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
    return {"path": path.relative_to(resolved_root).as_posix(), "changed": changed, "file": read_workspace_file(resolved_root, relative_path)}


def _git_environment() -> dict[str, str]:
    """Keep a read-only Git inspection independent of user credential config."""
    env = {key: value for key, value in os.environ.items() if not SENSITIVE_ENV.search(key)}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
        }
    )
    return env


def _run_git(root: Path, git: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run only an explicitly enumerated, non-interactive Git read command."""
    return subprocess.run(
        [git, "-C", str(root), "-c", "core.pager=cat", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_git_environment(),
        timeout=GIT_READ_TIMEOUT_SECONDS,
        check=False,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _git_error(result: subprocess.CompletedProcess[bytes]) -> str:
    detail = redact_text(result.stderr.decode("utf-8", errors="replace")).strip()
    return detail[:500] or "Git could not inspect this workspace."


def _workspace_change_status(code: str) -> str:
    """Map porcelain state to a small, presentation-only status vocabulary."""

    if code == "??":
        return "untracked"
    if "D" in code:
        return "deleted"
    if "R" in code:
        return "renamed"
    if "C" in code:
        return "copied"
    if "A" in code:
        return "added"
    if "M" in code or "T" in code or "U" in code:
        return "modified"
    return "changed"


def _safe_change_path(root: Path, value: str) -> str | None:
    """Discard unsafe or secret-shaped Git status paths before UI presentation."""

    try:
        return _safe_path(root, value, must_exist=False).relative_to(root).as_posix()
    except (OSError, RuntimeError, WorkspaceContextError):
        return None


def workspace_changes_context(root: str | os.PathLike[str] | None) -> dict[str, Any]:
    """List a bounded, safe Git change manifest without reading diff content.

    This is intentionally a discovery surface only. A user must still select one
    path before the existing single-file, redacted diff endpoint can inspect it.
    """

    resolved_root = _resolved_root(root)
    result: dict[str, Any] = {
        "available": False,
        "read_only": True,
        "reason": None,
        "changes": [],
        "counts": {},
        "truncated": False,
        "skipped": 0,
        "limits": {"max_changes": MAX_WORKSPACE_CHANGES, "max_status_bytes": MAX_WORKSPACE_STATUS_BYTES},
    }
    git = shutil.which("git")
    if not git:
        result["reason"] = "Git is not available on this computer."
        return result
    try:
        status = _run_git(resolved_root, git, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    except subprocess.TimeoutExpired:
        result["reason"] = "Git change review timed out without changing the workspace."
        return result
    except OSError:
        result["reason"] = "Git could not start for this workspace."
        return result
    if status.returncode:
        result["reason"] = _git_error(status)
        return result

    raw_status = status.stdout
    result["available"] = True
    if len(raw_status) > MAX_WORKSPACE_STATUS_BYTES:
        raw_status = raw_status[:MAX_WORKSPACE_STATUS_BYTES]
        result["truncated"] = True
    records = raw_status.split(b"\0")
    index = 0
    changes: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            result["skipped"] += 1
            continue
        code = record[:2].decode("ascii", errors="replace")
        if code == "!!":
            continue
        raw_path = record[3:].decode("utf-8", errors="replace")
        status_name = _workspace_change_status(code)
        previous_path = None
        if "R" in code or "C" in code:
            if index < len(records):
                previous_path = _safe_change_path(resolved_root, records[index].decode("utf-8", errors="replace"))
                index += 1
        path = _safe_change_path(resolved_root, raw_path)
        if not path:
            result["skipped"] += 1
            continue
        if len(changes) >= MAX_WORKSPACE_CHANGES:
            result["truncated"] = True
            break
        item: dict[str, Any] = {
            "path": path,
            "status": status_name,
            "reviewable": status_name != "deleted",
        }
        if previous_path and previous_path != path:
            item["previous_path"] = previous_path
        changes.append(item)
        counts[status_name] = counts.get(status_name, 0) + 1
    result["changes"] = changes
    result["counts"] = counts
    return result


def workspace_diff_context(root: str | os.PathLike[str] | None, relative_path: str) -> dict[str, Any]:
    """Return a bounded, non-executing Git review for one safe workspace file."""
    resolved_root = _resolved_root(root)
    file = read_workspace_file(resolved_root, relative_path)
    result: dict[str, Any] = {
        "path": file["path"],
        "diff_available": False,
        "changed": False,
        "status": None,
        "reason": None,
        "diff": None,
        "truncated": False,
        "file": file,
        "read_only": True,
        "limits": {"max_file_bytes": MAX_DIFF_FILE_BYTES, "max_diff_bytes": MAX_DIFF_BYTES},
    }
    if file["binary"]:
        result["reason"] = "Binary files have no text diff preview."
        return result
    if int(file["size"]) > MAX_DIFF_FILE_BYTES:
        result["reason"] = "This file is too large for the bounded diff preview."
        return result
    git = shutil.which("git")
    if not git:
        result["reason"] = "Git is not available on this computer."
        return result
    relative = str(file["path"])
    try:
        status = _run_git(resolved_root, git, "status", "--porcelain=v1", "--untracked-files=all", "--", relative)
        if status.returncode:
            result["reason"] = _git_error(status)
            return result
        result["status"] = redact_text(status.stdout.decode("utf-8", errors="replace")).strip() or "clean"

        previous_size = _run_git(resolved_root, git, "cat-file", "-s", f"HEAD:{relative}")
        if previous_size.returncode == 0:
            try:
                if int(previous_size.stdout.strip() or b"0") > MAX_DIFF_FILE_BYTES:
                    result["reason"] = "The previous version is too large for the bounded diff preview."
                    return result
            except ValueError:
                result["reason"] = "Git could not size the previous file version."
                return result

        diff = _run_git(
            resolved_root,
            git,
            "-c",
            "diff.external=",
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--unified=3",
            "HEAD",
            "--",
            relative,
        )
    except subprocess.TimeoutExpired:
        result["reason"] = "Git diff preview timed out without changing the workspace."
        return result
    except OSError:
        result["reason"] = "Git could not start for this workspace."
        return result

    if diff.returncode not in {0, 1}:
        result["reason"] = _git_error(diff)
        return result
    raw = diff.stdout
    result["truncated"] = len(raw) > MAX_DIFF_BYTES
    result["diff"] = redact_text(raw[:MAX_DIFF_BYTES].decode("utf-8", errors="replace"))
    result["changed"] = bool(result["diff"])
    result["diff_available"] = True
    if not result["changed"] and result["status"].startswith("??"):
        result["reason"] = "This is an untracked file, so it has no HEAD version to compare."
    return result
