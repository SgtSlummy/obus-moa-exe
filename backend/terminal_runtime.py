"""Local-only Windows ConPTY sessions for the OBus desktop workbench.

The design follows pywinpty's ``PtyProcess`` API and the single-reader/fan-out
pattern used by Windows agent harnesses: one daemon thread owns each ConPTY
read stream, then broadcasts bounded chunks to browser subscribers.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
import sys
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any


MAX_SESSIONS = 4
MAX_OUTPUT_CHARS = 250_000
MAX_SUBSCRIBER_CHUNKS = 512
_SENSITIVE_ENV = re.compile(
    r"(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|COOKIE|AUTHORIZATION|CREDENTIAL)",
    re.IGNORECASE,
)
_SPAWN_LOCK = threading.Lock()


class TerminalUnavailable(RuntimeError):
    """Raised when the native terminal dependency or shell is unavailable."""


def _load_pty_process():
    try:
        from winpty import PtyProcess
    except ImportError as exc:
        raise TerminalUnavailable("pywinpty is not installed in this OBus build") from exc
    return PtyProcess


def _terminal_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not _SENSITIVE_ENV.search(key)}
    env["PYTHONUTF8"] = "1"
    env["TERM"] = "xterm-256color"
    return env


def resolve_shell(shell: str) -> tuple[str, list[str]]:
    requested = str(shell or "pwsh").lower()
    names = {
        "pwsh": ("pwsh.exe", ["-NoLogo", "-NoProfile"]),
        "powershell": ("powershell.exe", ["-NoLogo", "-NoProfile"]),
        "cmd": ("cmd.exe", ["/Q"]),
    }
    if requested not in names:
        raise ValueError("shell must be pwsh, powershell, or cmd")
    name, args = names[requested]
    executable = shutil.which(name)
    if not executable:
        raise TerminalUnavailable(f"{name} is not installed")
    return executable, args


def _spawn_pty(pty_process: Any, argv: list[str], cwd: Path, rows: int, cols: int):
    """Spawn an external shell without leaking PyInstaller's DLL search path.

    A frozen PyInstaller process calls ``SetDllDirectoryW(sys._MEIPASS)``.
    Windows children inherit that setting and can load bundled DLLs instead of
    their system copies.  PowerShell then exits during startup.  Reset the
    process-wide setting only while ConPTY creates the child, serialize that
    small critical section, and restore it for OBus immediately afterward.
    """

    with _SPAWN_LOCK:
        restore_directory: str | None = None
        set_dll_directory = None
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            import ctypes

            set_dll_directory = ctypes.windll.kernel32.SetDllDirectoryW
            set_dll_directory.argtypes = [ctypes.c_wchar_p]
            set_dll_directory.restype = ctypes.c_bool
            if not set_dll_directory(None):
                raise ctypes.WinError()
            restore_directory = str(getattr(sys, "_MEIPASS", "") or "")
        try:
            return pty_process.spawn(
                argv,
                cwd=str(cwd),
                env=_terminal_environment(),
                dimensions=(rows, cols),
                # PyInstaller's one-file parent and a direct ConPTY child can
                # share control events; PowerShell then exits with
                # STATUS_CONTROL_C_EXIT.  The packaged winpty agent brokers
                # the child in its own console while retaining PTY semantics.
                backend=1 if getattr(sys, "frozen", False) else None,
            )
        finally:
            if set_dll_directory is not None and restore_directory:
                set_dll_directory(restore_directory)


class TerminalSession:
    def __init__(self, session_id: str, shell: str, cwd: Path, rows: int, cols: int) -> None:
        self.id = session_id
        self.shell = shell
        self.cwd = cwd
        self.rows = rows
        self.cols = cols
        self.created_at = time.time()
        self.updated_at = self.created_at
        self._pty: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._tail = ""
        self._subscribers: set[asyncio.Queue[str | None]] = set()
        self._write_lock = asyncio.Lock()

    async def start(self) -> None:
        executable, args = resolve_shell(self.shell)
        pty_process = _load_pty_process()
        self._loop = asyncio.get_running_loop()
        self._pty = await asyncio.to_thread(
            _spawn_pty,
            pty_process,
            [executable, *args],
            self.cwd,
            self.rows,
            self.cols,
        )
        self._reader = threading.Thread(
            target=self._reader_loop,
            name=f"obus-conpty-{self.id}",
            daemon=True,
        )
        self._reader.start()

    def _reader_loop(self) -> None:
        while not self._stop.is_set() and self._pty is not None:
            try:
                chunk = self._pty.read(8192)
            except (EOFError, OSError):
                break
            except Exception:
                break
            if not chunk:
                if not self.alive:
                    break
                time.sleep(0.01)
                continue
            loop = self._loop
            if loop is None or loop.is_closed():
                break
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._publish, str(chunk))
        loop = self._loop
        if loop is not None and not loop.is_closed():
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._publish_eof)

    def _publish(self, chunk: str) -> None:
        self.updated_at = time.time()
        self._tail = (self._tail + chunk)[-MAX_OUTPUT_CHARS:]
        for queue in tuple(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(chunk)

    def _publish_eof(self) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(None)

    @property
    def alive(self) -> bool:
        pty = self._pty
        if pty is None:
            return False
        with contextlib.suppress(Exception):
            return bool(pty.isalive())
        return False

    def snapshot(self) -> dict[str, object]:
        return {
            "id": self.id,
            "shell": self.shell,
            "cwd": str(self.cwd),
            "rows": self.rows,
            "cols": self.cols,
            "alive": self.alive,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def subscribe(self) -> asyncio.Queue[str | None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=MAX_SUBSCRIBER_CHUNKS)
        if self._tail:
            queue.put_nowait(self._tail)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str | None]) -> None:
        self._subscribers.discard(queue)

    async def write(self, data: str) -> None:
        if not data or not self.alive:
            return
        async with self._write_lock:
            await asyncio.to_thread(self._pty.write, data)
        self.updated_at = time.time()

    async def resize(self, rows: int, cols: int) -> None:
        if not self.alive:
            return
        await asyncio.to_thread(self._pty.setwinsize, rows, cols)
        self.rows, self.cols = rows, cols
        self.updated_at = time.time()

    async def close(self) -> None:
        self._stop.set()
        pty, self._pty = self._pty, None
        if pty is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(pty.close, True)
        self._publish_eof()


class TerminalRegistry:
    def __init__(self, limit: int = MAX_SESSIONS) -> None:
        self.limit = limit
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, shell: str, cwd: str | None, rows: int, cols: int) -> TerminalSession:
        root = Path(cwd).expanduser().resolve(strict=True) if cwd else Path.cwd().resolve()
        if not root.is_dir():
            raise ValueError("terminal cwd must be an existing directory")
        async with self._lock:
            dead = [key for key, value in self._sessions.items() if not value.alive]
            for key in dead:
                self._sessions.pop(key, None)
            if len(self._sessions) >= self.limit:
                raise RuntimeError(f"terminal session limit reached ({self.limit})")
            session = TerminalSession("term-" + uuid.uuid4().hex[:12], shell, root, rows, cols)
            await session.start()
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> TerminalSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError("terminal session not found") from exc

    def list(self) -> list[dict[str, object]]:
        return [session.snapshot() for session in self._sessions.values()]

    async def close(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            raise KeyError("terminal session not found")
        await session.close()

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        await asyncio.gather(*(session.close() for session in sessions), return_exceptions=True)


terminal_registry = TerminalRegistry()
