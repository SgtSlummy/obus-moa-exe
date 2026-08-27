from __future__ import annotations

import asyncio
import queue
from pathlib import Path
import sys

import backend.terminal_runtime as terminal_runtime


class FakePty:
    def __init__(self):
        self.input: list[str] = []
        self.size = (24, 80)
        self.alive = True
        self.output: queue.Queue[str | None] = queue.Queue()

    def read(self, _size):
        item = self.output.get(timeout=2)
        if item is None:
            raise EOFError
        return item

    def write(self, data):
        self.input.append(data)
        return len(data)

    def setwinsize(self, rows, cols):
        self.size = (rows, cols)

    def isalive(self):
        return self.alive

    def close(self, _force=False):
        self.alive = False
        self.output.put(None)


class FakePtyProcess:
    instance: FakePty | None = None

    @classmethod
    def spawn(cls, _argv, **_kwargs):
        cls.instance = FakePty()
        return cls.instance


def test_conpty_session_owns_single_reader_replays_output_and_controls_process(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(terminal_runtime, "_load_pty_process", lambda: FakePtyProcess)
    monkeypatch.setattr(terminal_runtime, "resolve_shell", lambda _shell: ("pwsh.exe", []))

    async def exercise():
        session = terminal_runtime.TerminalSession("term-test", "pwsh", tmp_path, 32, 120)
        await session.start()
        fake = FakePtyProcess.instance
        assert fake is not None
        fake.output.put("PowerShell ready\r\n")
        for _ in range(100):
            if "PowerShell ready" in session._tail:
                break
            await asyncio.sleep(0.01)
        subscriber = session.subscribe()
        assert "PowerShell ready" in await asyncio.wait_for(subscriber.get(), timeout=1)
        await session.write("Get-Location\r")
        assert fake.input == ["Get-Location\r"]
        await session.resize(40, 140)
        assert fake.size == (40, 140)
        await session.close()
        assert session.alive is False

    asyncio.run(exercise())


def test_terminal_environment_removes_credentials(monkeypatch):
    monkeypatch.setenv("OBUS_TEST_TOKEN", "secret")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("PATH", "safe-path")
    env = terminal_runtime._terminal_environment()
    assert "OBUS_TEST_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["PATH"] == "safe-path"
    assert env["TERM"] == "xterm-256color"


def test_frozen_terminal_uses_broker_backend(tmp_path: Path, monkeypatch):
    recorded: dict[str, object] = {}

    class RecordingPtyProcess:
        @staticmethod
        def spawn(_argv, **kwargs):
            recorded.update(kwargs)
            return FakePty()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(terminal_runtime, "_terminal_environment", lambda: {"PATH": "safe"})

    # Avoid mutating the real process DLL directory in a unit test; the
    # packaged smoke test covers that Win32 boundary end to end.
    monkeypatch.setattr(terminal_runtime.sys, "platform", "not-windows")
    result = terminal_runtime._spawn_pty(
        RecordingPtyProcess,
        ["pwsh.exe", "-NoProfile"],
        tmp_path,
        32,
        120,
    )

    assert isinstance(result, FakePty)
    assert recorded["backend"] == 1
