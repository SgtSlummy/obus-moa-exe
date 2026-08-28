"""Provider discovery and proactive objective scheduling for the Obus harness."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .codex_policy import build_codex_exec_command
from .execution_policy import classify_major_risk
from .secret_safety import redact_text


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ProviderRegistry:
    """Codex-primary registry with Ollama and OpenAI-compatible local adapters."""

    def __init__(self) -> None:
        self._last_discovery: list[dict[str, Any]] = []

    @staticmethod
    def _probe(url: str, timeout: float = 0.75) -> tuple[bool, dict[str, Any] | list[Any] | None]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return True, payload
        except (OSError, ValueError, urllib.error.URLError):
            return False, None

    def discover(self) -> list[dict[str, Any]]:
        providers: list[dict[str, Any]] = []
        codex_command = os.environ.get("OBUS_CODEX_COMMAND", "codex")
        codex_path = shutil.which(codex_command)
        providers.append({
            "id": "codex", "kind": "codex", "available": bool(codex_path),
            "primary": True, "endpoint": None, "models": [], "detail": codex_path or "command not found",
        })

        ollama_url = os.environ.get("OBUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        available, payload = self._probe(f"{ollama_url}/api/tags")
        models = [item.get("name", "") for item in (payload or {}).get("models", [])] if isinstance(payload, dict) else []
        providers.append({
            "id": "ollama", "kind": "ollama", "available": available,
            "primary": False, "endpoint": ollama_url, "models": [model for model in models if model],
            "detail": "ready" if available else "endpoint unavailable",
        })

        compatible_url = os.environ.get("OBUS_OPENAI_COMPATIBLE_URL", "").rstrip("/")
        if compatible_url:
            available, payload = self._probe(f"{compatible_url}/models")
            data = payload.get("data", []) if isinstance(payload, dict) else []
            models = [item.get("id", "") for item in data if isinstance(item, dict)]
            providers.append({
                "id": "openai-compatible", "kind": "openai-compatible", "available": available,
                "primary": False, "endpoint": compatible_url, "models": [model for model in models if model],
                "detail": "ready" if available else "endpoint unavailable",
            })
        self._last_discovery = providers
        return providers

    def capabilities(self) -> dict[str, Any]:
        providers = self.discover()
        return {"default": "codex", "providers": providers,
                "available": [provider["id"] for provider in providers if provider["available"]]}

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None,
                   timeout: int = 600) -> dict[str, Any]:
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                         headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError("provider returned a non-object response")
        return result

    @staticmethod
    def _workspace_tools() -> list[dict[str, Any]]:
        """Small, local-only tool surface shared by local model adapters."""

        return [
            {
                "type": "function",
                "function": {
                    "name": "list_workspace",
                    "description": "List safe files and folders beneath the selected workspace. Never reveals secrets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative folder, default is the workspace root."},
                            "max_depth": {"type": "integer", "minimum": 1, "maximum": 4},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read one non-secret UTF-8 text file beneath the selected workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string", "description": "Relative file path."}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_workspace",
                    "description": "Search safe UTF-8 workspace text for a literal query. Returns bounded path, line, and excerpt matches; secret-like files and content are excluded.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Literal text to find; this is not a regular expression."},
                            "path": {"type": "string", "description": "Optional relative folder to search."},
                            "case_sensitive": {"type": "boolean", "description": "Whether matching should preserve case; default false."},
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or replace one UTF-8 text file beneath the selected workspace. This is checkpointed and reversible.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path."},
                            "content": {"type": "string", "description": "Complete replacement text."},
                            "expected_sha256": {"type": "string", "description": "Required when replacing an existing file. Obtain this SHA-256 from read_file to prevent overwriting a changed file."},
                        },
                        "required": ["path", "content"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Apply one exact search-and-replace edit to a non-secret UTF-8 workspace file. Read the file first and supply its current SHA-256. Ambiguous matches are rejected unless replace_all is explicitly true.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative file path."},
                            "old_text": {"type": "string", "description": "Exact existing text to replace; include surrounding context when needed."},
                            "new_text": {"type": "string", "description": "Replacement text."},
                            "expected_sha256": {"type": "string", "description": "Required current SHA-256 from read_file, preventing a stale edit."},
                            "replace_all": {"type": "boolean", "description": "Replace every exact occurrence; default false."},
                        },
                        "required": ["path", "old_text", "new_text", "expected_sha256"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_verification",
                    "description": "Run one allowlisted local test, lint, build, or read-only git command in the selected workspace. No shell, installs, deletions, or system commands are permitted.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "For example: python -m pytest -q, npm test, cargo test, or git status."},
                            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 120},
                        },
                        "required": ["command"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    @staticmethod
    def _is_sensitive_workspace_path(path: Path) -> bool:
        name = path.name.casefold()
        protected_names = {
            ".env", ".netrc", ".npmrc", ".pypirc", "credentials.json", "auth.json", "token.json",
            "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "secrets.json",
        }
        protected_directories = {".aws", ".ssh", ".gnupg", ".config", ".git", ".hg", ".svn"}
        return (
            name in protected_names
            or name.startswith(".env.")
            or name.endswith(".secret")
            or "credentials" in name
            or path.suffix.casefold() in {".pem", ".key", ".pfx", ".p12", ".kdbx"}
            or any(part.casefold() in protected_directories for part in path.parts)
        )

    @staticmethod
    def _has_secret_like_text(content: str) -> bool:
        """Match the editor's conservative rule before any text reaches a model."""

        return redact_text(content, limit=max(1_000_000, len(content) + 1)) != content.strip()

    def _workspace_path(self, workspace: Path, raw_path: Any, *, allow_root: bool = False) -> Path:
        value = str(raw_path or ".").strip()
        candidate_input = Path(value)
        if candidate_input.is_absolute():
            raise ValueError("workspace paths must be relative")
        workspace = workspace.resolve()
        candidate = (workspace / candidate_input).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise ValueError("workspace path escapes the selected workspace") from exc
        if candidate == workspace and not allow_root:
            raise ValueError("a file path is required")
        if self._is_sensitive_workspace_path(candidate.relative_to(workspace)):
            raise ValueError("secret and repository-metadata paths are unavailable to local agents")
        return candidate

    def _list_workspace(self, workspace: Path, raw_path: Any, max_depth: Any) -> dict[str, Any]:
        root = self._workspace_path(workspace, raw_path, allow_root=True)
        if not root.is_dir():
            raise ValueError("the requested workspace folder does not exist")
        try:
            depth_limit = max(1, min(int(max_depth or 2), 4))
        except (TypeError, ValueError):
            depth_limit = 2
        workspace = workspace.resolve()
        entries: list[dict[str, Any]] = []

        def visit(folder: Path, depth: int) -> None:
            if len(entries) >= 200:
                return
            try:
                children = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
            except OSError:
                return
            for child in children:
                if len(entries) >= 200:
                    return
                try:
                    safe_child = self._workspace_path(workspace, child.relative_to(workspace), allow_root=True)
                except ValueError:
                    continue
                try:
                    is_directory = safe_child.is_dir()
                    entry = {"path": str(safe_child.relative_to(workspace)), "kind": "directory" if is_directory else "file"}
                    if not is_directory:
                        entry["bytes"] = safe_child.stat().st_size
                    entries.append(entry)
                    if is_directory and depth < depth_limit and not safe_child.is_symlink():
                        visit(safe_child, depth + 1)
                except OSError:
                    continue

        visit(root, 1)
        return {"ok": True, "root": str(root.relative_to(workspace)) or ".", "entries": entries,
                "truncated": len(entries) >= 200}

    def _read_workspace_file(self, workspace: Path, raw_path: Any) -> dict[str, Any]:
        target = self._workspace_path(workspace, raw_path)
        if not target.is_file():
            raise ValueError("the requested workspace file does not exist")
        try:
            raw = target.read_bytes()
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("the requested file is not UTF-8 text") from exc
        if len(raw) > 128 * 1024:
            raise ValueError("the requested file is larger than the 128 KiB local-agent read limit")
        if self._has_secret_like_text(content):
            raise ValueError("the requested workspace file contains secret-like content and is unavailable to local agents")
        return {
            "ok": True, "path": str(target.relative_to(workspace.resolve())), "content": content,
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        }

    def _search_workspace(self, workspace: Path, query: Any, raw_path: Any, case_sensitive: Any,
                          max_results: Any) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search_workspace requires a literal query")
        needle = query.strip()
        if len(needle) > 256:
            raise ValueError("search_workspace queries are limited to 256 characters")
        root = self._workspace_path(workspace, raw_path or ".", allow_root=True)
        if not root.is_dir():
            raise ValueError("the requested workspace search path is not a directory")
        try:
            limit = max(1, min(int(max_results or 50), 100))
        except (TypeError, ValueError):
            limit = 50
        workspace = workspace.resolve()
        compare_needle = needle if bool(case_sensitive) else needle.casefold()
        matches: list[dict[str, Any]] = []
        files_scanned = 0
        skipped = 0
        scan_limit = 1_200
        exhausted = False
        for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            safe_directories: list[str] = []
            for name in sorted(directories, key=str.casefold):
                try:
                    candidate = self._workspace_path(workspace, (current_path / name).relative_to(workspace), allow_root=True)
                except ValueError:
                    skipped += 1
                    continue
                if candidate.is_symlink():
                    skipped += 1
                    continue
                safe_directories.append(name)
            directories[:] = safe_directories
            for name in sorted(filenames, key=str.casefold):
                if len(matches) >= limit or files_scanned >= scan_limit:
                    exhausted = True
                    break
                try:
                    target = self._workspace_path(workspace, (current_path / name).relative_to(workspace))
                    if not target.is_file() or target.stat().st_size > 128 * 1024:
                        skipped += 1
                        continue
                    content = target.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError, ValueError):
                    skipped += 1
                    continue
                files_scanned += 1
                if self._has_secret_like_text(content):
                    skipped += 1
                    continue
                for line_number, line in enumerate(content.splitlines(), start=1):
                    haystack = line if bool(case_sensitive) else line.casefold()
                    if compare_needle in haystack:
                        matches.append({
                            "path": str(target.relative_to(workspace)), "line": line_number,
                            "text": redact_text(line, limit=500),
                        })
                        if len(matches) >= limit:
                            exhausted = True
                            break
            if exhausted:
                break
        return {
            "ok": True, "query": needle, "matches": matches, "files_scanned": files_scanned,
            "skipped": skipped, "truncated": exhausted,
        }

    def _write_workspace_file(self, workspace: Path, raw_path: Any, content: Any,
                              expected_sha256: Any = None) -> dict[str, Any]:
        target = self._workspace_path(workspace, raw_path)
        if not isinstance(content, str):
            raise ValueError("write_file content must be text")
        updated = content.encode("utf-8")
        if len(updated) > 512 * 1024:
            raise ValueError("write_file content exceeds the 512 KiB local-agent limit")
        if self._has_secret_like_text(content):
            raise ValueError("writing secret-like content is not permitted for local agents")
        risks = classify_major_risk(content)
        if risks:
            raise ValueError("writing major-risk instructions is not permitted: " + ", ".join(risks))
        existed = target.exists()
        original_mode: int | None = None
        if existed:
            if not target.is_file():
                raise ValueError("write_file cannot replace a workspace directory")
            try:
                original = target.read_bytes()
                original_mode = target.stat().st_mode
            except OSError as exc:
                raise ValueError("the existing workspace file could not be prepared for an atomic write") from exc
            if len(original) > 512 * 1024 or b"\x00" in original:
                raise ValueError("the existing workspace file is not a supported text replacement target")
            try:
                original_text = original.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("the existing workspace file is not UTF-8 text") from exc
            if self._has_secret_like_text(original_text):
                raise ValueError("the existing workspace file contains secret-like content and cannot be replaced")
            actual_sha256 = hashlib.sha256(original).hexdigest()
            if not isinstance(expected_sha256, str) or actual_sha256 != expected_sha256:
                raise ValueError("the existing workspace file changed; read it again and provide its current sha256")
        elif expected_sha256 not in (None, ""):
            raise ValueError("expected_sha256 is only valid when replacing an existing workspace file")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            descriptor, temp_path = tempfile.mkstemp(prefix=f".{target.name}.obus-", suffix=".tmp", dir=str(target.parent))
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
            temp_path = None
            if original_mode is not None:
                os.chmod(target, original_mode)
        except OSError as exc:
            raise ValueError("the workspace file could not be written atomically") from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        return {
            "ok": True, "path": str(target.relative_to(workspace.resolve())), "bytes": len(updated),
            "created": not existed,
        }

    def _edit_workspace_file(self, workspace: Path, raw_path: Any, old_text: Any, new_text: Any,
                             expected_sha256: Any, replace_all: Any = False) -> dict[str, Any]:
        """Apply an exact, checksum-guarded replacement without fuzzy matching."""

        if not isinstance(old_text, str) or not isinstance(new_text, str):
            raise ValueError("edit_file old_text and new_text must be text")
        if not old_text:
            raise ValueError("edit_file old_text must not be empty; use write_file for an intentional full-file replacement")
        if old_text == new_text:
            raise ValueError("edit_file old_text and new_text must differ")
        if not isinstance(expected_sha256, str) or not expected_sha256:
            raise ValueError("edit_file requires the current sha256 from read_file")
        if not isinstance(replace_all, bool):
            raise ValueError("edit_file replace_all must be a boolean")

        before = self._read_workspace_file(workspace, raw_path)
        if before["sha256"] != expected_sha256:
            raise ValueError("the existing workspace file changed; read it again and provide its current sha256")
        content = before["content"]
        occurrences = content.count(old_text)
        if occurrences == 0:
            raise ValueError("edit_file old_text did not exactly match; read the file again and use its exact text")
        if occurrences > 1 and not replace_all:
            raise ValueError("edit_file old_text matched multiple locations; include unique surrounding context or set replace_all to true")

        replacements = occurrences if replace_all else 1
        updated = content.replace(old_text, new_text, replacements)
        write_result = self._write_workspace_file(workspace, raw_path, updated, expected_sha256)
        diff_lines = list(difflib.unified_diff(
            content.splitlines(keepends=True), updated.splitlines(keepends=True),
            fromfile=str(before["path"]), tofile=str(before["path"]), n=3,
        ))
        diff = "".join(diff_lines)
        return {
            **write_result,
            "replacements": replacements,
            "sha256": hashlib.sha256(updated.encode("utf-8")).hexdigest(),
            "diff": diff[-16_000:],
            "diff_truncated": len(diff) > 16_000,
        }

    @staticmethod
    def _allowed_verification_command(command: Any) -> list[str]:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("run_verification requires a command")
        if any(token in command for token in ("\r", "\n", "&&", "||", ";", "|", ">", "<", "`", "$(")):
            raise ValueError("run_verification does not permit shell syntax")
        try:
            args = shlex.split(command, posix=os.name != "nt")
        except ValueError as exc:
            raise ValueError("run_verification command could not be parsed") from exc
        args = [item.strip('"') for item in args]
        if not args:
            raise ValueError("run_verification requires a command")
        if any(separator in args[0] for separator in ("/", "\\")):
            raise ValueError("run_verification requires an allowlisted command name, not a file path")
        executable = Path(args[0]).name.casefold()
        lowered = [item.casefold() for item in args[1:]]
        python_module = lowered[1] if len(lowered) >= 2 and lowered[:1] == ["-m"] else ""
        python_module_allowed = (
            python_module in {"pytest", "unittest", "compileall", "mypy", "pyright", "pylint"}
            or (python_module == "ruff" and lowered[2:3] in (["check"],))
            or (python_module == "ruff" and lowered[2:4] == ["format", "--check"])
            or (python_module == "black" and "--check" in lowered[2:])
        )
        git_unsafe_option = any(
            flag in {"--exec", "-c", "--ext-diff", "--no-index", "--textconv", "--output"}
            or flag.startswith("--output=")
            for flag in lowered[1:]
        )
        allowed = (
            executable in {"pytest", "pytest.exe"}
            or (executable in {"python", "python.exe", "py"} and python_module_allowed)
            or (executable == "ruff" and lowered[:1] == ["check"])
            or (executable == "ruff" and lowered[:2] == ["format", "--check"])
            or (executable == "black" and "--check" in lowered)
            or (executable in {"mypy", "pyright", "pylint"})
            or (executable == "eslint" and "--fix" not in lowered)
            or (executable == "prettier" and lowered[:1] == ["--check"])
            or (executable in {"tsc", "tsc.cmd"} and "--noemit" in lowered)
            or (executable in {"npm", "npm.cmd"} and lowered and (lowered[0] == "test" or lowered[:2] in (["run", "test"], ["run", "lint"], ["run", "build"], ["run", "check"])))
            or (executable in {"node", "node.exe"} and lowered[:1] == ["--test"])
            or (executable == "cargo" and lowered[:1] in (["test"], ["check"], ["clippy"], ["build"]))
            or (executable == "go" and lowered[:1] in (["test"], ["vet"], ["build"]))
            or (executable == "dotnet" and lowered[:1] in (["test"], ["build"]))
            or (executable == "git" and lowered[:1] in (["status"], ["diff"], ["log"])
                and not git_unsafe_option)
        )
        if not allowed:
            raise ValueError("only local test, lint, build, and read-only git verification commands are allowed")
        return args

    def _run_verification(self, workspace: Path, command: Any, timeout_seconds: Any,
                          cancellation: threading.Event) -> dict[str, Any]:
        args = self._allowed_verification_command(command)
        try:
            timeout = max(1, min(int(timeout_seconds or 60), 120))
        except (TypeError, ValueError):
            timeout = 60
        with tempfile.TemporaryFile(mode="w+b") as output:
            process = subprocess.Popen(args, cwd=workspace, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT, shell=False)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancellation.wait(0.1):
                    process.terminate()
                    raise InterruptedError("task cancelled")
                if time.monotonic() >= deadline:
                    process.terminate()
                    raise RuntimeError(f"verification command timed out after {timeout} seconds")
            output.seek(0)
            text = output.read(16_000).decode("utf-8", errors="replace")
        return {
            "ok": process.returncode == 0,
            "returncode": process.returncode,
            "output": redact_text(text[-12_000:], limit=12_000, parse_json=False),
        }

    def _execute_workspace_tool(self, workspace: Path, name: str, arguments: dict[str, Any],
                                cancellation: threading.Event) -> dict[str, Any]:
        if name == "list_workspace":
            return self._list_workspace(workspace, arguments.get("path", "."), arguments.get("max_depth", 2))
        if name == "read_file":
            return self._read_workspace_file(workspace, arguments.get("path"))
        if name == "search_workspace":
            return self._search_workspace(
                workspace, arguments.get("query"), arguments.get("path", "."),
                arguments.get("case_sensitive", False), arguments.get("max_results", 50),
            )
        if name == "write_file":
            return self._write_workspace_file(
                workspace, arguments.get("path"), arguments.get("content"), arguments.get("expected_sha256"),
            )
        if name == "edit_file":
            return self._edit_workspace_file(
                workspace, arguments.get("path"), arguments.get("old_text"), arguments.get("new_text"),
                arguments.get("expected_sha256"), arguments.get("replace_all", False),
            )
        if name == "run_verification":
            return self._run_verification(workspace, arguments.get("command"), arguments.get("timeout_seconds"), cancellation)
        raise ValueError(f"unknown local workspace tool: {name}")

    @staticmethod
    def _normalise_tool_calls(raw_calls: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_calls or []):
            if not isinstance(raw, dict):
                continue
            function = raw.get("function") if isinstance(raw.get("function"), dict) else raw
            name = str(function.get("name") or "").strip()
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            calls.append({"id": str(raw.get("id") or f"call-{index}"), "name": name,
                          "arguments": arguments if isinstance(arguments, dict) else {}})
        return calls

    @staticmethod
    def _ollama_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            item = {"role": message["role"], "content": str(message.get("content") or "")}
            if message["role"] == "assistant" and message.get("tool_calls"):
                item["tool_calls"] = [
                    {"function": {"name": call["name"], "arguments": call["arguments"]}}
                    for call in message["tool_calls"]
                ]
            converted.append(item)
        return converted

    @staticmethod
    def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for message in messages:
            item = {"role": message["role"], "content": str(message.get("content") or "")}
            if message["role"] == "assistant" and message.get("tool_calls"):
                item["tool_calls"] = [
                    {"id": call["id"], "type": "function",
                     "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])}}
                    for call in message["tool_calls"]
                ]
            if message["role"] == "tool":
                item["tool_call_id"] = message["tool_call_id"]
            converted.append(item)
        return converted

    def _workspace_tool_event_payload(self, provider: str, call: dict[str, Any], status: str,
                                      ok: bool | None = None) -> dict[str, Any]:
        """Keep lifecycle receipts useful without surfacing secret-like paths."""

        raw_path = str(call.get("arguments", {}).get("path") or "")[:512]
        path = "" if raw_path and self._is_sensitive_workspace_path(Path(raw_path)) else raw_path
        payload: dict[str, Any] = {
            "provider": provider, "tool": str(call.get("name") or ""), "status": status, "path": path,
        }
        if ok is not None:
            payload["ok"] = ok
        return payload

    @staticmethod
    def _verification_receipt_event_payload(provider: str, result: dict[str, Any]) -> dict[str, Any]:
        """Return a short, secret-safe terminal receipt without echoing the command."""

        ok = bool(result.get("ok"))
        payload: dict[str, Any] = {
            "provider": provider,
            "status": "passed" if ok else "failed",
            "ok": ok,
        }
        if isinstance(result.get("returncode"), int):
            payload["returncode"] = result["returncode"]
        preview = result.get("output") or result.get("error") or ""
        if preview:
            payload["output"] = redact_text(str(preview), limit=2_000, parse_json=False)
        return payload

    def _run_workspace_tool_loop(self, task: dict[str, Any], cancellation: threading.Event,
                                 emit: Callable[[str, dict[str, Any]], None], provider: str, model: str,
                                 request: Callable[[list[dict[str, Any]]], dict[str, Any]]) -> str:
        workspace = Path(str(task["workspace"])).resolve()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": (
                "You are a guarded local workspace agent. Complete the user's objective with the supplied tools. "
                "Inspect the workspace before making conclusions, make only focused reversible edits, and verify them "
                "with an allowlisted local command when useful. Use edit_file with exact old and new text for focused "
                "changes; read a file first and pass its sha256 to edit_file or write_file when it already exists. "
                "Never request secrets, network access, package installs, "
                "deletions, or system actions. Do not claim completion until you have called at least one workspace tool."
            )},
            {"role": "user", "content": (
                "This task was explicitly resumed after OBus restarted. Before taking any action, inspect the current "
                "workspace and the visible task history/checkpoint. Do not repeat or assume any uncertain side effect. "
                "Once a safe point is verified, continue ordinary local inspection, focused workspace edits, and local "
                "verification autonomously; do not ask for confirmation between those routine steps. Pause and clearly "
                "request approval before any destructive, external, credential-handling, or hardware-affecting action.\n\n"
                if task.get("resumed_after_interruption") else ""
            ) + str(task["objective"])},
        ]
        tool_steps = 0
        pending_tool_failure = False
        for _turn in range(12):
            if cancellation.is_set():
                raise InterruptedError("task cancelled")
            assistant = request(messages)
            calls = self._normalise_tool_calls(assistant.get("tool_calls"))
            content = str(assistant.get("content") or "").strip()
            if not calls:
                if tool_steps == 0:
                    raise RuntimeError("local model returned a response without inspecting or acting in the workspace")
                if pending_tool_failure:
                    raise RuntimeError("local model ended its workspace run with an unresolved tool failure")
                if not content:
                    raise RuntimeError("local model ended its workspace run without a final summary")
                emit("provider.output", {"provider": provider, "text": content[-16_000:], "tool_steps": tool_steps})
                return content
            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            for call in calls:
                tool_steps += 1
                emit("provider.tool", self._workspace_tool_event_payload(provider, call, "running"))
                try:
                    result = self._execute_workspace_tool(workspace, call["name"], call["arguments"], cancellation)
                except InterruptedError:
                    raise
                except Exception as exc:
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                pending_tool_failure = not bool(result.get("ok"))
                emit("provider.tool", self._workspace_tool_event_payload(
                    provider, call, "succeeded" if result.get("ok") else "failed", bool(result.get("ok")),
                ))
                if call["name"] == "run_verification":
                    emit("provider.verification", self._verification_receipt_event_payload(provider, result))
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
        raise RuntimeError("local model exhausted the 12-step workspace tool budget without completing the task")

    def run(self, task: dict[str, Any], cancellation: threading.Event,
            emit: Callable[[str, dict[str, Any]], None]) -> str:
        provider = str(task.get("provider") or "codex")
        if provider == "codex":
            return self._run_codex(task, cancellation, emit)
        if provider == "ollama":
            return self._run_ollama(task, cancellation, emit)
        if provider == "openai-compatible":
            return self._run_openai_compatible(task, cancellation, emit)
        raise ValueError(f"unsupported provider: {provider}")

    def _run_codex(self, task: dict[str, Any], cancellation: threading.Event,
                   emit: Callable[[str, dict[str, Any]], None]) -> str:
        command = os.environ.get("OBUS_CODEX_COMMAND", "codex")
        if os.name == "nt" and not Path(command).suffix:
            command = shutil.which(command) or command
        model = os.environ.get("OBUS_CODEX_MODEL", "")
        output_path: Path | None = None
        try:
            # Codex writes its user-facing answer separately from its useful but
            # noisy process stream.  Keep that stream only for failure evidence.
            with tempfile.NamedTemporaryFile(prefix="obus-codex-", suffix=".txt", delete=False) as handle:
                output_path = Path(handle.name)
            args = build_codex_exec_command(
                command,
                (
                    "This task was explicitly resumed after OBus restarted. Before taking any action, inspect the current "
                    "workspace and the visible task history/checkpoint. Do not repeat or assume any uncertain side effect. "
                    "Once a safe point is verified, continue ordinary local inspection, focused workspace edits, and local "
                    "verification autonomously; do not ask for confirmation between those routine steps. Pause and clearly "
                    "request approval before any destructive, external, credential-handling, or hardware-affecting action.\n\n"
                    if task.get("resumed_after_interruption") else ""
                ) + str(task["objective"]),
                model=model or None,
                output_path=output_path,
            )
            # Python's Windows shell path is required only for .cmd/.bat shims;
            # it preserves argv quoting for the user objective. Native executables
            # continue through CreateProcess without a shell.
            batch_launcher = os.name == "nt" and Path(args[0]).suffix.lower() in {".cmd", ".bat"}
            emit("provider.started", {"provider": "codex", "model": model or "default"})
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(args, cwd=task["workspace"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       shell=batch_launcher,
                                       text=True, encoding="utf-8", errors="replace", creationflags=flags)
            chunks: list[str] = []
            while process.poll() is None:
                if cancellation.wait(0.2):
                    process.terminate()
                    raise InterruptedError("task cancelled")
            if process.stdout:
                chunks.append(process.stdout.read())
            diagnostics = "".join(chunks).strip()
            if process.returncode != 0:
                raise RuntimeError(f"Codex exited with code {process.returncode}: {diagnostics[-2000:]}")
            output = output_path.read_text(encoding="utf-8", errors="replace").strip()
            if not output:
                raise RuntimeError("Codex returned no final message")
            emit("provider.output", {"provider": "codex", "text": output[-16000:]})
            return output
        finally:
            if output_path is not None:
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _run_ollama(self, task: dict[str, Any], cancellation: threading.Event,
                    emit: Callable[[str, dict[str, Any]], None]) -> str:
        if cancellation.is_set():
            raise InterruptedError("task cancelled")
        endpoint = os.environ.get("OBUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        model = str(task.get("model") or os.environ.get("OBUS_OLLAMA_MODEL", "llama3.2"))
        try:
            context_window = int(task.get("context_window") or 0)
        except (TypeError, ValueError):
            context_window = 0
        if not 2_048 <= context_window <= 2_000_000:
            context_window = 0
        started = {"provider": "ollama", "model": model}
        if context_window:
            started["context_window"] = context_window
        emit("provider.started", started)

        def request(messages: list[dict[str, Any]]) -> dict[str, Any]:
            payload: dict[str, Any] = {
                "model": model, "messages": self._ollama_messages(messages),
                "tools": self._workspace_tools(), "stream": False,
            }
            if context_window:
                payload["options"] = {"num_ctx": context_window}
            result = self._post_json(f"{endpoint}/api/chat", payload)
            message = result.get("message")
            if not isinstance(message, dict):
                raise RuntimeError("Ollama returned no chat message")
            return {"content": message.get("content") or "", "tool_calls": message.get("tool_calls") or []}

        return self._run_workspace_tool_loop(task, cancellation, emit, "ollama", model, request)

    def _run_openai_compatible(self, task: dict[str, Any], cancellation: threading.Event,
                               emit: Callable[[str, dict[str, Any]], None]) -> str:
        if cancellation.is_set():
            raise InterruptedError("task cancelled")
        endpoint = os.environ.get("OBUS_OPENAI_COMPATIBLE_URL", "").rstrip("/")
        if not endpoint:
            raise RuntimeError("OBUS_OPENAI_COMPATIBLE_URL is not configured")
        model = str(task.get("model") or os.environ.get("OBUS_OPENAI_COMPATIBLE_MODEL", "local-model"))
        token = os.environ.get("OBUS_OPENAI_COMPATIBLE_TOKEN", "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        emit("provider.started", {"provider": "openai-compatible", "model": model})

        def request(messages: list[dict[str, Any]]) -> dict[str, Any]:
            result = self._post_json(f"{endpoint}/chat/completions", {
                "model": model, "messages": self._openai_messages(messages),
                "tools": self._workspace_tools(), "stream": False,
            }, headers)
            choices = result.get("choices") or []
            message = choices[0].get("message") if choices and isinstance(choices[0], dict) else None
            if not isinstance(message, dict):
                raise RuntimeError("OpenAI-compatible provider returned no chat message")
            return {"content": message.get("content") or "", "tool_calls": message.get("tool_calls") or []}

        return self._run_workspace_tool_loop(task, cancellation, emit, "openai-compatible", model, request)


class ObjectiveScheduler:
    """Durable interval scheduler for ordinary, bounded workspace objectives.

    Scheduled objectives deliberately have a narrower authority than one-off
    harness tasks: anything that matches the major-risk policy is never
    started on a timer.  A running prior task also prevents overlap, which
    keeps an interval from silently multiplying autonomous work.
    """

    def __init__(self, database: Path, submit: Callable[..., dict[str, Any]], poll_seconds: float = 1.0,
                 task_active: Callable[[str], bool] | None = None):
        self.database = database
        self.submit = submit
        self.poll_seconds = max(0.1, poll_seconds)
        self.task_active = task_active or (lambda _task_id: False)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS harness_objectives (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, objective TEXT NOT NULL,
                    workspace TEXT NOT NULL, provider TEXT NOT NULL DEFAULT 'codex',
                    interval_seconds INTEGER NOT NULL, priority INTEGER NOT NULL DEFAULT 50,
                    enabled INTEGER NOT NULL DEFAULT 1, next_run_at REAL NOT NULL,
                    last_run_at REAL, last_task_id TEXT, last_error TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_harness_objectives_due
                    ON harness_objectives(enabled, next_run_at);
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(harness_objectives)")}
            if "last_error" not in columns:
                connection.execute("ALTER TABLE harness_objectives ADD COLUMN last_error TEXT")

    def create(self, name: str, objective: str, workspace: Path, interval_seconds: int,
               provider: str = "codex", priority: int = 50, enabled: bool = True) -> dict[str, Any]:
        now = time.time()
        item_id = uuid.uuid4().hex
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO harness_objectives(id,name,objective,workspace,provider,interval_seconds,priority,enabled,"
                "next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (item_id, name, objective, str(workspace.resolve()), provider, max(1, interval_seconds),
                 max(0, min(priority, 100)), int(enabled), now + max(1, interval_seconds), utc_now(), utc_now()),
            )
        return self.get(item_id)

    def get(self, item_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM harness_objectives WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise KeyError(item_id)
        return self._public(row)

    def list(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM harness_objectives ORDER BY created_at DESC").fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row) | {"enabled": bool(row["enabled"])}

    def set_enabled(self, item_id: str, enabled: bool) -> dict[str, Any]:
        if enabled:
            item = self.get(item_id)
            risks = classify_major_risk(str(item.get("objective") or ""))
            if risks:
                raise ValueError("Major-risk objectives cannot be scheduled: " + ", ".join(risks))
        with self._connection() as connection:
            cursor = connection.execute("UPDATE harness_objectives SET enabled=?,last_error=NULL,updated_at=? WHERE id=?",
                                        (int(enabled), utc_now(), item_id))
            if cursor.rowcount == 0:
                raise KeyError(item_id)
        return self.get(item_id)

    def delete(self, item_id: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM harness_objectives WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                raise KeyError(item_id)

    def run_due(self, now: float | None = None) -> list[str]:
        current = time.time() if now is None else now
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM harness_objectives WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at", (current,)
            ).fetchall()
        task_ids: list[str] = []
        for row in rows:
            risks = classify_major_risk(str(row["objective"] or ""))
            if risks:
                with self._connection() as connection:
                    connection.execute(
                        "UPDATE harness_objectives SET enabled=0,last_error=?,updated_at=? WHERE id=?",
                        ("Disabled: scheduled objectives cannot perform major-risk work (" + ", ".join(risks) + ")",
                         utc_now(), row["id"]),
                    )
                continue
            prior_task_id = str(row["last_task_id"] or "")
            if prior_task_id and self.task_active(prior_task_id):
                with self._connection() as connection:
                    connection.execute(
                        "UPDATE harness_objectives SET next_run_at=?,last_error=?,updated_at=? WHERE id=?",
                        (current + row["interval_seconds"], "Previous run is still active; this interval was skipped.",
                         utc_now(), row["id"]),
                    )
                continue
            try:
                workspace = Path(row["workspace"]).expanduser().resolve(strict=True)
                if not workspace.is_dir():
                    raise RuntimeError("configured workspace is not a directory")
                task = self.submit(row["objective"], workspace, source="scheduler",
                                   priority=row["priority"], provider=row["provider"])
            except Exception as exc:
                with self._connection() as connection:
                    connection.execute(
                        "UPDATE harness_objectives SET enabled=0,last_error=?,updated_at=? WHERE id=?",
                        (f"Disabled: unable to start scheduled run ({str(exc)[:400]})", utc_now(), row["id"]),
                    )
                continue
            task_ids.append(str(task["id"]))
            with self._connection() as connection:
                connection.execute(
                    "UPDATE harness_objectives SET last_run_at=?,last_task_id=?,next_run_at=?,last_error=NULL,updated_at=? WHERE id=?",
                    (current, task["id"], current + row["interval_seconds"], utc_now(), row["id"]),
                )
        return task_ids

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="obus-objective-scheduler", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_seconds):
            try:
                self.run_due()
            except Exception:
                continue

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
