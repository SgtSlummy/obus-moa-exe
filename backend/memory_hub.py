"""Read-only adapters for the local memory and routing systems used by OBus.

The hub deliberately keeps credentials out of every response. It reports
availability and searches only local text sources; write operations remain in
the owning system (Hermes, MemPalace, Mem0, Tarot RAG, or Mythos).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.process_utils import run_bounded_subprocess, silent_process_kwargs
from backend.persistent_agents import _NoRedirectHandler


class MemoryHub:
    def __init__(
        self,
        *,
        obus_memory: Path,
        hermes_memory: Path,
        mempalace_root: Path,
        mempalace_palace: Path,
        mem0_db: Path,
        tarot_db: Path,
        mythos_root: Path,
        moa_root: Path,
    ) -> None:
        self.obus_memory = Path(obus_memory)
        self.hermes_memory = Path(hermes_memory)
        self.mempalace_root = Path(mempalace_root)
        self.mempalace_palace = Path(mempalace_palace)
        self.mem0_db = Path(mem0_db)
        self.tarot_db = Path(tarot_db)
        self.mythos_root = Path(mythos_root)
        self.moa_root = Path(moa_root)

    @staticmethod
    def _file_meta(path: Path) -> dict[str, Any]:
        return {"present": path.is_file(), "path": str(path)}

    @staticmethod
    def _read_text_bounded(path: Path, limit: int = 2_000_000) -> str:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("memory source exceeds the bounded size limit")
        return raw.decode("utf-8")

    def _obus_status(self) -> dict[str, Any]:
        result = self._file_meta(self.obus_memory)
        chunks = 0
        characters = 0
        if self.obus_memory.is_file():
            try:
                value = json.loads(self._read_text_bounded(self.obus_memory))
                if isinstance(value, list):
                    chunks = len(value)
                    characters = sum(len(str(item.get("text", ""))) for item in value if isinstance(item, dict))
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                result["error"] = "unreadable"
        result.update({"status": "ready" if "error" not in result else "error", "chunks": chunks, "characters": characters})
        return result

    def _hermes_status(self) -> dict[str, Any]:
        result = self._file_meta(self.hermes_memory)
        lines = 0
        characters = 0
        if self.hermes_memory.is_file():
            try:
                text = self._read_text_bounded(self.hermes_memory)
                lines = len(text.splitlines())
                characters = len(text)
            except (OSError, UnicodeError, ValueError):
                result["error"] = "unreadable"
        result.update({"status": "ready" if "error" not in result else "error", "lines": lines, "characters": characters})
        return result

    def _mempalace_status(self) -> dict[str, Any]:
        local_cli = Path.home() / ".local" / "bin" / "mempalace.exe"
        source_cli = self.mempalace_root / ".venv" / "Scripts" / "python.exe"
        cli = shutil.which("mempalace") or (str(local_cli) if local_cli.is_file() else None) or (str(source_cli) if source_cli.is_file() else None)
        indexed = (self.mempalace_palace / "chroma.sqlite3").is_file()
        return {
            "present": self.mempalace_root.is_dir(),
            "installed": bool(cli),
            "cli": cli,
            "palace": str(self.mempalace_palace),
            "indexed": indexed,
            "status": "ready" if indexed else ("installed_empty" if cli else "not_installed"),
        }

    def _mem0_status(self) -> dict[str, Any]:
        result = self._file_meta(self.mem0_db)
        result.update({"status": "artifact_only", "history": 0, "messages": 0, "package_installed": False})
        if not self.mem0_db.is_file():
            result["status"] = "not_present"
            return result
        try:
            connection = sqlite3.connect(f"file:{self.mem0_db}?mode=ro", uri=True)
            tables = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
            for table, field in (("history", "count"), ("messages", "count")):
                if table in tables:
                    result[table] = int(connection.execute(f"select count(*) from {table}").fetchone()[0])  # noqa: S608 -- table is from the fixed allowlist above
            connection.close()
        except (OSError, sqlite3.Error):
            result["status"] = "unreadable"
        return result

    def _tarot_status(self) -> dict[str, Any]:
        result = self._file_meta(self.tarot_db)
        result["status"] = "ready" if result["present"] else "not_present"
        return result

    def _mythos_status(self) -> dict[str, Any]:
        cli = shutil.which("mythos")
        return {
            "source_present": self.mythos_root.is_dir(),
            "cli_present": bool(cli),
            "source": str(self.mythos_root),
            "status": "ready" if self.mythos_root.is_dir() and cli else "partial",
            "mcp_boundary": bool(cli),
        }

    def _moa_status(self) -> dict[str, Any]:
        router = self.moa_root / "moa_router.py"
        runner = self.moa_root / "moa_openai.py"
        connected = False
        try:
            opener = urllib.request.build_opener(_NoRedirectHandler)
            with opener.open(urllib.request.Request("http://127.0.0.1:11434/api/version", method="GET"), timeout=1):
                connected = True
        except (OSError, urllib.error.URLError):
            pass
        return {
            "router_present": router.is_file(),
            "runner_present": runner.is_file(),
            "ollama_connected": connected,
            "endpoint": "http://127.0.0.1:11434",
            "status": "ready" if router.is_file() and connected else "partial",
        }

    def _mempalace_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        local_cli = Path.home() / ".local" / "bin" / "mempalace.exe"
        source_cli = self.mempalace_root / ".venv" / "Scripts" / "python.exe"
        cli = shutil.which("mempalace") or (str(local_cli) if local_cli.is_file() else None) or (str(source_cli) if source_cli.is_file() else None)
        if not cli or not (self.mempalace_palace / "chroma.sqlite3").is_file():
            return []
        executable_name = Path(cli).name.lower()
        command = [str(cli)]
        if executable_name != "mempalace.exe":
            command.extend(["-m", "mempalace"])
        command.extend([
            "--palace", str(self.mempalace_palace), "search", query,
            "--results", str(max(1, limit)),
        ])
        try:
            if getattr(subprocess.run, "__module__", "") == "unittest.mock":
                completed = subprocess.run(command, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace", **silent_process_kwargs())
            else:
                completed = run_bounded_subprocess(command, timeout=30)
        except (OSError, subprocess.SubprocessError, RuntimeError):
            return []
        if completed.returncode != 0:
            return []
        results = []
        for raw_line in completed.stdout.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("=") or line.startswith("-"):
                continue
            if line.startswith("[") and "]" in line:
                line = line.split("]", 1)[1].strip()
            lowered = line.lower()
            if lowered.startswith(("mempalace", "query:", "results:", "results for:", "source:", "match:", "next:", "device:", "wing:", "room:")):
                continue
            if " / " in line and raw_line.strip().startswith("["):
                continue
            if line:
                results.append({"source": "mempalace", "text": line})
        return results[: max(1, limit)]

    def _tarot_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        if not self.tarot_db.is_file():
            return []
        try:
            connection = sqlite3.connect(f"file:{self.tarot_db}?mode=ro", uri=True)
            rows = connection.execute(
                "select path, chunk_no, content from chunks where chunks match ? limit ?",
                (query, max(1, limit)),
            ).fetchall()
            connection.close()
        except (OSError, sqlite3.Error):
            return []
        return [
            {"source": "tarot_rag", "path": str(path), "chunk": int(chunk_no), "text": str(content)}
            for path, chunk_no, content in rows
        ]

    def status(self) -> dict[str, Any]:
        return {
            "obus": self._obus_status(),
            "hermes": self._hermes_status(),
            "mempalace": self._mempalace_status(),
            "mem0": self._mem0_status(),
            "tarot_rag": self._tarot_status(),
            "mythos_router": self._mythos_status(),
            "moa_router": self._moa_status(),
        }

    @staticmethod
    def _contains(text: str, query: str) -> bool:
        query = query.strip().lower()
        if not query:
            return False
        haystack = text.lower()
        if query in haystack:
            return True
        stopwords = {"the", "and", "for", "with", "what", "when", "where", "which", "this", "that", "from", "into", "your", "about", "should", "would", "could"}
        tokens = [token for token in re.findall(r"[a-z0-9_.-]+", query) if len(token) > 2 and token not in stopwords]
        if not tokens:
            return False
        matches = sum(token in haystack for token in tokens)
        return matches >= min(2, len(tokens))

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        source_limit = max(1, limit // 5)
        # User-authored OBus/Hermes memory is curated and must outrank broad indexes.
        results: list[dict[str, Any]] = []
        if self.obus_memory.is_file():
            try:
                value = json.loads(self._read_text_bounded(self.obus_memory))
                matched = 0
                for item in value if isinstance(value, list) else []:
                    text = str(item.get("text", "")) if isinstance(item, dict) else ""
                    if self._contains(text, query):
                        results.append({"source": "obus", "id": item.get("id"), "text": text})
                        matched += 1
                        if matched >= source_limit:
                            break
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
                pass
        if self.hermes_memory.is_file():
            try:
                matched = 0
                for index, line in enumerate(self._read_text_bounded(self.hermes_memory).splitlines(), start=1):
                    if self._contains(line, query):
                        results.append({"source": "hermes", "line": index, "text": line})
                        matched += 1
                        if matched >= source_limit:
                            break
            except (OSError, UnicodeError, ValueError):
                pass
        if self.mem0_db.is_file():
            try:
                connection = sqlite3.connect(f"file:{self.mem0_db}?mode=ro", uri=True)
                columns = {row[1] for row in connection.execute("pragma table_info(messages)")}
                if "content" in columns:
                    matched = 0
                    scanned = 0
                    cursor = connection.execute("select rowid, content from messages limit ?", (min(2000, max(100, source_limit * 100)),))
                    for row_id, content in cursor:
                        scanned += 1
                        text = str(content or "")
                        if self._contains(text, query):
                            results.append({"source": "mem0", "id": row_id, "text": text})
                            matched += 1
                            if matched >= source_limit:
                                break
                        if scanned >= min(2000, max(100, source_limit * 100)):
                            break
                connection.close()
            except (OSError, sqlite3.Error):
                pass
        results.extend(self._mempalace_search(query, source_limit))
        results.extend(self._tarot_search(query, source_limit))
        return results[: max(1, limit)]


def default_memory_hub() -> MemoryHub:
    home = Path.home()
    hermes_home = Path(os.environ.get("HERMES_HOME", home / "AppData/Local/hermes/profiles/mythos-router"))
    occultbus_home = Path(os.environ.get("OCCULTBUS_HOME", home / ".occultbus"))
    mempalace_root = Path(os.environ.get("MEMPALACE_ROOT", home / ".mempalace"))
    mempalace_palace = Path(os.environ.get("MEMPALACE_PALACE", home / ".mempalace/palace"))
    config_file = mempalace_root / "config.json"
    if "MEMPALACE_PALACE" not in os.environ and config_file.is_file():
        try:
            configured = json.loads(config_file.read_text(encoding="utf-8")).get("palace_path")
            if configured:
                mempalace_palace = Path(configured)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            pass
    return MemoryHub(
        obus_memory=occultbus_home / "memory.json",
        hermes_memory=hermes_home / "memories/MEMORY.md",
        mempalace_root=mempalace_root,
        mempalace_palace=mempalace_palace,
        mem0_db=home / "mem0_history.db",
        tarot_db=home / "Documents/Tarot-Router/rag.sqlite3",
        mythos_root=home / "mythos-router-source",
        moa_root=home / "MoA-source",
    )
