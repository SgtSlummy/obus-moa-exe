"""Windows-safe subprocess options and bounded child-process execution."""
from __future__ import annotations

import os
import subprocess
import threading
from typing import Any

MAX_SUBPROCESS_OUTPUT_BYTES = 4_000_000


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
    limit: int = MAX_SUBPROCESS_OUTPUT_BYTES,
) -> subprocess.CompletedProcess[str]:
    """Run a child with bounded concurrent stdout/stderr capture."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        **silent_process_kwargs(),
    )
    stdout = bytearray()
    stderr = bytearray()
    overflow = threading.Event()
    budget = [limit]
    budget_lock = threading.Lock()

    def drain(stream, target: bytearray) -> None:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            with budget_lock:
                if len(chunk) > budget[0]:
                    overflow.set()
                    try:
                        process.kill()
                    except OSError:
                        pass
                    return
                budget[0] -= len(chunk)
            if len(target) + len(chunk) > limit:
                overflow.set()
                try:
                    process.kill()
                except OSError:
                    pass
                return
            target.extend(chunk)

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
        try:
            process.kill()
        finally:
            process.wait()
        return_code = process.returncode
    finally:
        for thread in threads:
            thread.join(timeout=2)
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
