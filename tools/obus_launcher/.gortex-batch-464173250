"""Launch the packaged local OBus dashboard on Windows.

The launcher owns process readiness only. OBus itself owns model residency and
memory integration status, so this module invokes its documented local APIs
instead of guessing provider names or private endpoints.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = int(os.environ.get("OBUS_PORT", "38173"))
DASHBOARD_URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = f"http://{HOST}:{PORT}/health"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
WARMUP_URL = f"http://{HOST}:{PORT}/api/warmup"
MEMORY_STATUS_URL = f"http://{HOST}:{PORT}/api/integrations/memory"
STARTUP_TIMEOUT_SECONDS = 45


def _json_request(url: str, *, method: str = "GET", body: dict | None = None, timeout: int = 10) -> dict | None:
    """Return a decoded local JSON response, or None when the service is absent."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else None
    except (OSError, urllib.error.URLError, ValueError, UnicodeDecodeError):
        return None


def is_dashboard_healthy() -> bool:
    """Require OBus's canonical health contract before opening the browser."""
    payload = _json_request(HEALTH_URL, timeout=3)
    return bool(payload and payload.get("status") == "ok" and payload.get("service") == "obus-moa")


def wait_for_dashboard(timeout_seconds: int = STARTUP_TIMEOUT_SECONDS) -> bool:
    """Wait only until OBus's health endpoint is ready."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_dashboard_healthy():
            return True
        time.sleep(0.5)
    return False


def silent_process_kwargs() -> dict[str, Any]:
    """Hide the backend child console on Windows without suppressing failures."""
    if os.name != "nt":
        return {}
    startupinfo = getattr(subprocess, "STARTUPINFO")()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW")
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE")
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW"),
        "startupinfo": startupinfo,
    }


def backend_command() -> list[str]:
    """Re-enter the source script or packaged executable in dedicated server mode."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--serve"]
    return [sys.executable, str(Path(__file__).resolve()), "--serve"]


def ensure_backend_running() -> bool:
    """Start one backend only when the canonical health endpoint is unavailable."""
    if is_dashboard_healthy():
        return True
    try:
        subprocess.Popen(
            backend_command(),
            cwd=str(Path.cwd()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **silent_process_kwargs(),
        )
    except OSError:
        return False
    return wait_for_dashboard()


def collect_readiness() -> dict[str, Any]:
    """Probe actual OBus readiness services and request one selected-model warmup."""
    health = _json_request(HEALTH_URL, timeout=3)
    ollama = _json_request(OLLAMA_TAGS_URL, timeout=3)
    warmup = _json_request(WARMUP_URL, method="POST", body={}, timeout=310)
    memory = _json_request(MEMORY_STATUS_URL, timeout=10)
    return {
        "dashboard_healthy": bool(health and health.get("status") == "ok"),
        "ollama": ollama or {"connected": False, "error": "Ollama is unavailable"},
        "warmup": warmup or {"status": "unavailable"},
        "memory": memory or {"status": "unavailable"},
    }


def show_error(message: str) -> None:
    """Show a visible error when a windowed EXE cannot start its backend."""
    if os.name == "nt":
        getattr(ctypes, "windll").user32.MessageBoxW(
            0, message, "OBus Launcher", 0x10
        )
    else:
        print(message, file=sys.stderr)


def launch_dashboard() -> int:
    """Start OBus, prove health, show the UI, then finish readiness warmup."""
    if not ensure_backend_running():
        show_error(f"OBus did not become healthy at {HEALTH_URL} within {STARTUP_TIMEOUT_SECONDS} seconds.")
        return 1

    # Health is the launch gate. Noncritical warmup must not delay visible UI.
    webbrowser.open(DASHBOARD_URL)
    collect_readiness()
    return 0


def serve_backend() -> None:
    """Run the packaged FastAPI app as the launcher child process."""
    if sys.stdout is None or sys.stderr is None:
        try:
            log_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Obus" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            windowed_stream = (log_dir / "launcher.log").open(
                "a", encoding="utf-8", buffering=1
            )
        except OSError:
            windowed_stream = open(os.devnull, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = windowed_stream
        if sys.stderr is None:
            sys.stderr = windowed_stream

    if not getattr(sys, "frozen", False):
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
    from backend.main import app
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve_backend()
    else:
        raise SystemExit(launch_dashboard())