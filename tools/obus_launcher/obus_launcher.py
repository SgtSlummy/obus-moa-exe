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
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
BIND_HOST = os.environ.get("OBUS_HOST", HOST).strip() or HOST
PORT = int(os.environ.get("OBUS_PORT", "38173"))
DASHBOARD_URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = f"http://{HOST}:{PORT}/health"
OLLAMA_TAGS_URL = os.environ.get("OBUS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
WARMUP_URL = f"http://{HOST}:{PORT}/api/warmup"
MEMORY_STATUS_URL = f"http://{HOST}:{PORT}/api/integrations/memory"
STARTUP_TIMEOUT_SECONDS = 45
STARTUP_REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "Obus"
BACKEND_PROCESS: subprocess.Popen | None = None


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
        global BACKEND_PROCESS
        BACKEND_PROCESS = subprocess.Popen(
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


def startup_enabled() -> bool:
    """Return whether this executable is registered for per-user Windows startup."""
    if os.name != "nt":
        return False
    try:
        import winreg
        with getattr(winreg, "OpenKey")(getattr(winreg, "HKEY_CURRENT_USER"), STARTUP_REGISTRY_PATH) as key:
            command, _ = getattr(winreg, "QueryValueEx")(key, STARTUP_VALUE_NAME)
        return str(Path(sys.executable).resolve()).casefold() in command.casefold()
    except (FileNotFoundError, OSError):
        return False


def set_startup_enabled(enabled: bool) -> None:
    """Enable or disable launch-at-login without requiring administrator access."""
    if os.name != "nt":
        raise OSError("Launch at login is supported only on Windows")
    import winreg
    with getattr(winreg, "CreateKey")(getattr(winreg, "HKEY_CURRENT_USER"), STARTUP_REGISTRY_PATH) as key:
        if enabled:
            getattr(winreg, "SetValueEx")(key, STARTUP_VALUE_NAME, 0, getattr(winreg, "REG_SZ"), f'"{Path(sys.executable).resolve()}" --startup')
        else:
            try:
                getattr(winreg, "DeleteValue")(key, STARTUP_VALUE_NAME)
            except FileNotFoundError:
                pass


def stop_owned_backend() -> None:
    """Stop only the backend process created by this launcher instance."""
    if BACKEND_PROCESS is not None and BACKEND_PROCESS.poll() is None:
        BACKEND_PROCESS.terminate()


def run_system_tray() -> bool:
    """Run OBus in the notification area until the user chooses Exit."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    image = Image.new("RGBA", (64, 64), "#17152a")
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill="#7657ff")
    draw.text((22, 18), "O", fill="white")

    def toggle_startup(icon, _item):
        set_startup_enabled(not startup_enabled())
        icon.update_menu()

    def exit_obus(icon, _item):
        stop_owned_backend()
        icon.stop()

    icon = pystray.Icon(
        "Obus", image, "Obus — Codex agent runtime",
        menu=pystray.Menu(
            pystray.MenuItem("Open Obus", lambda _icon, _item: webbrowser.open(DASHBOARD_URL), default=True),
            pystray.MenuItem("Start with Windows", toggle_startup, checked=lambda _item: startup_enabled()),
            pystray.MenuItem("Exit", exit_obus),
        ),
    )
    icon.run()
    return True


def launch_dashboard(*, show_browser: bool = True, keep_alive: bool = True) -> int:
    """Start OBus, show the UI promptly, then remain available in the tray."""
    if not ensure_backend_running():
        show_error(f"OBus did not become healthy at {HEALTH_URL} within {STARTUP_TIMEOUT_SECONDS} seconds.")
        return 1

    if show_browser:
        webbrowser.open(DASHBOARD_URL)
    threading.Thread(target=collect_readiness, name="obus-readiness", daemon=True).start()
    if keep_alive:
        run_system_tray()
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

    uvicorn.run(app, host=BIND_HOST, port=PORT)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve_backend()
    else:
        raise SystemExit(launch_dashboard(show_browser="--startup" not in sys.argv))
