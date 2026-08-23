#!/usr/bin/env python3
"""
OBus Launcher - First-run setup detection and dashboard launch
"""
import sys
import os
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Set up paths before any imports
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OBus"
DATA_DIR = Path(os.environ.get('OCCULTBUS_HOME', DEFAULT_DATA_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETUP_FILE = DATA_DIR / 'setup_complete.json'
APP_PORT = 38173
APP_URL = f"http://127.0.0.1:{APP_PORT}/"
HEALTH_URL = f"http://127.0.0.1:{APP_PORT}/health"
INSTANCE_MUTEX_HANDLE = None
INSTANCE_MUTEX_NAME = "Local\\OBusMoaRuntime"
EDGE_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
)


def _create_windows_mutex() -> tuple[object | None, bool]:
    if os.name != "nt":
        return object(), False
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateMutexW(None, False, INSTANCE_MUTEX_NAME)
    return handle, ctypes.get_last_error() == 183


def acquire_single_instance() -> bool:
    """Own the one backend/tray slot; later launches only reopen the window."""
    global INSTANCE_MUTEX_HANDLE
    if INSTANCE_MUTEX_HANDLE is not None:
        return True
    handle, already_exists = _create_windows_mutex()
    if already_exists:
        if os.name == "nt" and handle:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(handle)
        return False
    INSTANCE_MUTEX_HANDLE = handle
    return True


def is_setup_complete() -> bool:
    """Check if first-run setup has been completed"""
    if SETUP_FILE.exists():
        try:
            import json
            with open(SETUP_FILE) as f:
                state = json.load(f)
                return state.get('setup_complete', False)
        except Exception:
            pass
    return False


def mark_setup_complete(stage: str = "complete"):
    """Mark setup as complete with stage"""
    import json
    state = {
        'setup_complete': True,
        'setup_stage': stage,
        'completed_at': datetime.now(timezone.utc).isoformat() + 'Z'
    }
    with open(SETUP_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def find_edge_executable() -> Path | None:
    for candidate in EDGE_CANDIDATES:
        if candidate.is_file():
            return candidate
    discovered = shutil.which("msedge.exe") or shutil.which("msedge")
    return Path(discovered) if discovered else None


def build_standalone_window_command(url: str, edge_executable: Path) -> list[str]:
    """Build a browser-chrome-free Edge app-window command."""
    return [str(edge_executable), f"--app={url}", "--start-windowed"]


def activate_existing_app_window() -> bool:
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if title.value == "OBus MOA":
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return False
    user32.ShowWindow(found[0], 9)
    user32.SetForegroundWindow(found[0])
    return True


def open_app_window(url: str) -> bool:
    """Open OBus as a standalone app window, falling back to the default browser."""
    edge = find_edge_executable()
    if edge:
        from backend.process_utils import silent_process_kwargs
        subprocess.Popen(
            build_standalone_window_command(url, edge),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **silent_process_kwargs(),
        )
        return True
    try:
        import webbrowser
        return bool(webbrowser.open(url))
    except Exception:
        print(f"Please open: {url}")
        return False


def ensure_app_window(url: str) -> bool:
    return activate_existing_app_window() or open_app_window(url)


def _tray_image():
    from PIL import Image, ImageDraw
    icon_path = APP_DIR / "assets" / "obus_emblem.ico"
    if icon_path.is_file():
        return Image.open(icon_path).convert("RGBA")
    image = Image.new("RGBA", (64, 64), "#090c17")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), radius=14, outline="#f5c451", width=4)
    draw.ellipse((27, 27, 37, 37), fill="#55d8ff")
    return image


def start_system_tray(open_action, exit_action):
    """Keep OBus alive in the Windows notification area after its window closes."""
    try:
        import pystray
        icon = pystray.Icon(
            "OBus",
            _tray_image(),
            "OBus — GPU runtime active",
            menu=pystray.Menu(
                pystray.MenuItem("Open OBus", lambda _icon, _item: open_action(), default=True),
                pystray.MenuItem("Exit OBus", lambda tray, _item: (exit_action(), tray.stop())),
            ),
        )
        threading.Thread(target=icon.run, name="obus-system-tray", daemon=True).start()
        return icon
    except (ImportError, OSError):
        return None


def wait_for_server(url: str, attempts: int = 80, delay: float = 0.02) -> bool:
    """Wait until the local HTTP server responds before opening the browser.

    The 20 ms retry cadence keeps startup responsiveness below the requested
    30 ms bound without busy-spinning the launcher.
    """
    for _ in range(attempts):
        try:
            response = urllib.request.urlopen(url, timeout=1)
            close = getattr(response, "close", None)
            if close:
                close()
            return True
        except OSError:
            time.sleep(delay)
    return False


def open_window_when_ready():
    if wait_for_server(HEALTH_URL):
        open_app_window(APP_URL)


def main():
    """Main entry point with first-run logic"""
    print("=" * 50)
    print("OBus MOA Runtime")
    print("=" * 50)

    if not acquire_single_instance():
        if wait_for_server(HEALTH_URL, attempts=120, delay=0.05):
            ensure_app_window(APP_URL)
        return
    
    if wait_for_server(HEALTH_URL, attempts=1, delay=0):
        ensure_app_window(APP_URL)
        return

    print("\nStarting local dashboard server...")
    # Start the server in the foreground so the EXE owns its lifecycle.
    try:
        sys.path.insert(0, str(APP_DIR))
        from backend.main import app
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=APP_PORT, log_level="warning", access_log=False))
        tray = start_system_tray(lambda: open_app_window(APP_URL), lambda: setattr(server, "should_exit", True))
        threading.Thread(target=open_window_when_ready, daemon=True).start()
        server.run()
        if tray:
            tray.stop()
    except ImportError as e:
        print("\nError: Could not import backend modules")
        print(f"   {e}")
        print(f"\nPlease ensure all backend files are in place:")
        print(f"   - {APP_DIR}/backend/")
        sys.exit(1)


if __name__ == '__main__':
    main()