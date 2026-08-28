"""Windows-safe subprocess options and bounded child-process execution."""
from __future__ import annotations

import os
import subprocess
import threading
from typing import Any

MAX_SUBPROCESS_OUTPUT_BYTES = 4_000_000


def _normalize_windows_command(command: list[str]) -> list[str]:
    """Execute Windows batch launchers through ``cmd.exe`` with argv quoting.

    ``CreateProcess`` cannot directly execute a ``.cmd``/``.bat`` file, which
    otherwise presents as WinError 5 when a desktop provider uses a Node CLI
    shim. Keep the command as argv until this final Windows-only adaptation so
    callers retain their output, timeout, and process-tree safeguards.
    """

    if os.name != "nt" or not command:
        return command
    if os.path.splitext(command[0])[1].lower() not in {".cmd", ".bat"}:
        return command
    comspec = os.environ.get("COMSPEC") or "cmd.exe"
    # ``call`` keeps the batch wrapper in this cmd.exe process and preserves
    # the final quoted prompt as one argv item for Node-style CLI shims.
    return [comspec, "/d", "/s", "/c", f"call {subprocess.list2cmdline(command)}"]


def terminate_process_tree(process: subprocess.Popen) -> None:
    if os.name == "nt" and process.pid:
        try:
            result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if result.returncode == 0:
                return
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def silent_process_kwargs() -> dict[str, Any]:
    """Hide child console windows on Windows while preserving captured output."""
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }


def run_bounded_subprocess(
    command: list[str],
    timeout: int | float,
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    limit: int = MAX_SUBPROCESS_OUTPUT_BYTES,
) -> subprocess.CompletedProcess[str]:
    """Run a child with bounded concurrent stdout/stderr capture."""
    command = _normalize_windows_command(command)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        **silent_process_kwargs(),
    )
    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()
    budget = [limit]
    budget_lock = threading.Lock()

    def drain(stream, target: bytearray) -> None:
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                with budget_lock:
                    if len(chunk) > budget[0]:
                        overflow.set()
                        terminate_process_tree(process)
                        return
                    budget[0] -= len(chunk)
                if len(target) + len(chunk) > limit:
                    overflow.set()
                    terminate_process_tree(process)
                    return
                target.extend(chunk)
        except (OSError, ValueError):
            # The parent closes pipes after the child exits or is terminated.
            return

    threads = [
        threading.Thread(target=drain, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    timeout_error = None
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        timeout_error = exc
        terminate_process_tree(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return_code = process.returncode
    finally:
        for thread in threads:
            thread.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
    if timeout_error is not None:
        raise timeout_error
    if len(stdout) + len(stderr) > limit or overflow.is_set():
        raise RuntimeError("Local subprocess output exceeded the bounded response limit")
    return subprocess.CompletedProcess(
        command,
        return_code,
        bytes(stdout).decode("utf-8", "replace"),
        bytes(stderr).decode("utf-8", "replace"),
    )
