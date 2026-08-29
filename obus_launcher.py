#!/usr/bin/env python3
"""
OBus Launcher - First-run setup detection and dashboard launch
"""
import sys
import os
import json
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Set up paths before any imports
APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "OBus"
DATA_DIR = Path(os.environ.get('OCCULTBUS_HOME', DEFAULT_DATA_DIR))
DATA_DIR.mkdir(parents=True, exist_ok=True)
LEGACY_DATA_DIR = Path.home() / '.occultbus'
if DATA_DIR != LEGACY_DATA_DIR:
    for filename in ('obus_state.json', 'memory.json', 'usage.json'):
        source = LEGACY_DATA_DIR / filename
        destination = DATA_DIR / filename
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
os.environ.setdefault('OCCULTBUS_HOME', str(DATA_DIR))

SETUP_FILE = DATA_DIR / 'setup_complete.json'
APP_PORT = int(os.environ.get("OBUS_PORT", "38173"))
APP_URL = f"http://127.0.0.1:{APP_PORT}/"
HEALTH_URL = f"http://127.0.0.1:{APP_PORT}/health"
DESKTOP_PAGE_IDS = frozenset({"dashboard", "runtime", "runs"})
INSTANCE_MUTEX_HANDLE = None
INSTANCE_MUTEX_NAME = f"Local\\OBusMoaRuntime-{APP_PORT}"
EDGE_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
)
DESKTOP_WINDOW_TITLE = "OBus MOA"
NATIVE_WINDOW = None
NATIVE_WINDOW_LOCK = threading.RLock()
NATIVE_WINDOW_EXIT_REQUESTED = threading.Event()
STARTUP_LOG_DIR = DATA_DIR / "logs" / "startup"
STARTUP_LOG_MAX_FILES = 16
STARTUP_DIAGNOSTIC_PATH = STARTUP_LOG_DIR / (
    f"obus-startup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{os.getpid()}.json"
)
STARTUP_DIAGNOSTIC = {
    "started_at": datetime.now(timezone.utc).isoformat(),
    "app_port": APP_PORT,
    "events": [],
}


def record_startup_event(event: str, **details: object) -> None:
    """Persist a bounded, secret-safe diagnostic timeline for this launch."""

    safe_details = {}
    for key, value in details.items():
        if isinstance(value, bool | int | float):
            safe_details[key] = value
        elif isinstance(value, str):
            safe_details[key] = value[:160]
    STARTUP_DIAGNOSTIC["events"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "details": safe_details,
    })
    STARTUP_DIAGNOSTIC["events"] = STARTUP_DIAGNOSTIC["events"][-32:]
    try:
        STARTUP_LOG_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = STARTUP_DIAGNOSTIC_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(STARTUP_DIAGNOSTIC, indent=2), encoding="utf-8")
        os.replace(temp_path, STARTUP_DIAGNOSTIC_PATH)
        old_logs = sorted(STARTUP_LOG_DIR.glob("obus-startup-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old_log in old_logs[STARTUP_LOG_MAX_FILES:]:
            old_log.unlink(missing_ok=True)
    except OSError:
        # Diagnostics must never prevent a local desktop startup.
        pass


def show_startup_error(message: str) -> None:
    """Surface a startup failure even when no OBus window could be created."""

    print(message, file=sys.stderr)
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "OBus could not start", 0x10)
    except (AttributeError, OSError):
        pass


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


def desktop_page_url(page: str = "dashboard") -> str:
    """Return a local UI activation URL for a known surface and optional task ID.

    Tray state can contain only an opaque local task identifier.  Keep that
    identifier bounded here so opening a task cannot turn into a general URL
    handoff or disclose task text through the native host.
    """
    requested, separator, task_id = str(page or "dashboard").partition("&task=")
    if requested not in DESKTOP_PAGE_IDS:
        return APP_URL
    if not separator or not re.fullmatch(r"[A-Za-z0-9-]{1,96}", task_id):
        return APP_URL if requested == "dashboard" else f"{APP_URL}?{urllib.parse.urlencode({'page': requested})}"
    return f"{APP_URL}?{urllib.parse.urlencode({'page': requested, 'task': task_id})}"


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
        if title.value == DESKTOP_WINDOW_TITLE:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return False
    user32.ShowWindow(found[0], 9)
    user32.SetForegroundWindow(found[0])
    return True


def native_desktop_host_enabled() -> bool:
    """Whether normal Windows launches should prefer OBus's own native webview."""

    mode = os.environ.get("OBUS_DESKTOP_HOST", "native").strip().casefold()
    return os.name == "nt" and mode not in {"edge", "browser", "disabled", "off", "0"}


def native_webview_available() -> bool:
    if not native_desktop_host_enabled():
        return False
    try:
        import webview  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def obus_health_state(url: str) -> str:
    """Return ready, unavailable, or unexpected for the canonical OBus endpoint."""

    try:
        response = urllib.request.urlopen(url, timeout=1)
        try:
            body = response.read(64 * 1024)
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        payload = json.loads(body.decode("utf-8"))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return "unavailable"
    if isinstance(payload, dict) and payload.get("status") == "ok" and payload.get("service") == "obus-moa":
        return "ready"
    return "unexpected"


def focus_native_window(url: str) -> bool:
    """Navigate and focus the in-process native window when it is active."""

    with NATIVE_WINDOW_LOCK:
        window = NATIVE_WINDOW
    if window is None:
        return False
    try:
        window.load_url(url)
        window.restore()
        window.show()
        return True
    except (AttributeError, OSError, RuntimeError):
        return False


def close_native_window(*, allow_app_exit: bool = False) -> None:
    """Close the native window, optionally allowing a full desktop shutdown."""

    if allow_app_exit:
        NATIVE_WINDOW_EXIT_REQUESTED.set()

    with NATIVE_WINDOW_LOCK:
        window = NATIVE_WINDOW
    if window is None:
        return
    try:
        window.destroy()
    except (AttributeError, OSError, RuntimeError):
        pass


def hide_native_window_to_tray(window) -> bool | None:
    """Keep a normal native-window close available from the system tray.

    pywebview cancels a close when a ``closing`` event handler returns False.
    The explicit tray exit path sets ``NATIVE_WINDOW_EXIT_REQUESTED`` first,
    allowing ``destroy`` to close the host and then its local server.
    """

    if NATIVE_WINDOW_EXIT_REQUESTED.is_set():
        return None
    try:
        window.hide()
    except (AttributeError, OSError, RuntimeError):
        return None
    record_startup_event("native_window_hidden_to_tray")
    return False


def run_native_desktop_window(url: str, *, hide_to_tray_on_close: bool = False) -> bool:
    """Run OBus in a native Windows WebView2 host on the main thread.

    pywebview is deliberately optional: a missing WebView2 runtime or host
    dependency simply returns False so the existing Edge/browser fallback
    stays available.  The loopback API remains the only application backend.
    """

    if not native_webview_available():
        return False
    try:
        import webview

        NATIVE_WINDOW_EXIT_REQUESTED.clear()
        icon = APP_DIR / "assets" / "obus_emblem.ico"
        window = webview.create_window(
            DESKTOP_WINDOW_TITLE,
            url,
            width=1440,
            height=920,
            min_size=(1024, 660),
            background_color="#090c17",
            confirm_close=False,
        )
        if window is None:
            return False
        global NATIVE_WINDOW
        with NATIVE_WINDOW_LOCK:
            NATIVE_WINDOW = window
        if hide_to_tray_on_close:
            window.events.closing += hide_native_window_to_tray
        record_startup_event("native_window_starting", host="edgechromium")
        webview.start(
            gui="edgechromium",
            private_mode=True,
            icon=str(icon) if icon.is_file() else None,
        )
        record_startup_event("native_window_closed")
        return True
    except Exception as exc:  # Optional UI host failures must retain the safe fallback.
        record_startup_event("native_window_failed", error_type=type(exc).__name__)
        print(f"Native desktop host unavailable; using browser fallback: {type(exc).__name__}")
        return False
    finally:
        with NATIVE_WINDOW_LOCK:
            NATIVE_WINDOW = None
        NATIVE_WINDOW_EXIT_REQUESTED.clear()


def open_app_window(url: str) -> bool:
    """Open OBus as a standalone app window, falling back to the default browser."""
    if focus_native_window(url):
        return True
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


TRAY_STATUS_POLL_SECONDS = 2.0


def stop_system_tray(icon) -> None:
    """Stop a tray icon and its read-only local status monitor."""
    monitor_stop = getattr(icon, "_obus_status_monitor_stop", None)
    if monitor_stop is not None:
        monitor_stop.set()
    icon.stop()


def start_system_tray(open_action, exit_action, open_page_action=None):
    """Keep OBus alive in the notification area with redacted local activity state."""
    try:
        import json
        import urllib.error
        import urllib.request

        import pystray

        if open_page_action is None:
            open_page_action = lambda _page: open_action()

        state = {
            "status": "starting",
            "muted": False,
            "active": None,
            "pending_approvals": None,
            "codex_active": 0,
            "codex_pending_approvals": 0,
            "task_states": None,
            "latest_outcome_task_id": None,
            "attention_tasks": 0,
            "provider": None,
            "ready": False,
        }
        monitor_stop = threading.Event()
        icon_ref = {}

        def request_json(path: str, method: str = "GET", payload=None):
            body = None if payload is None else json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                f"{APP_URL}{path}", data=body, method=method,
                headers={"Content-Type": "application/json"} if body else {},
            )
            with urllib.request.urlopen(request, timeout=0.4) as response:
                return json.loads(response.read().decode("utf-8"))

        def refresh_status():
            transition = {
                "became_ready": False,
                "activity_started": False,
                "activity_stopped": False,
                "approval_required": False,
            }
            try:
                health = request_json("/api/harness/health")
                active = int(health.get("active_tasks", health.get("active", health.get("active_objectives", 0))) or 0)
                provider = str(health.get("provider_default", health.get("provider", health.get("default_provider", "codex"))))
                previous_active = state["active"]
                previous_pending_approvals = state["pending_approvals"]
                try:
                    approvals = request_json("/api/harness/approvals?limit=50").get("approvals", [])
                    pending_approvals = sum(
                        1 for approval in approvals
                        if isinstance(approval, dict) and approval.get("status") == "pending"
                    )
                except (OSError, ValueError, urllib.error.URLError):
                    pending_approvals = int(previous_pending_approvals or 0)
                try:
                    tasks = request_json("/api/harness/tasks?limit=50").get("tasks", [])
                    task_states = {
                        str(task.get("id")): str(task.get("state"))
                        for task in tasks if isinstance(task, dict) and task.get("id")
                    }
                    previous_task_states = state["task_states"]
                    outcome_ids = [
                        task_id for task_id in task_states
                        if task_states[task_id] in {"succeeded", "failed", "interrupted"}
                        and previous_task_states is not None
                        and previous_task_states.get(task_id) != task_states[task_id]
                    ]
                    transition["task_outcomes"] = [task_states[task_id] for task_id in outcome_ids]
                    if outcome_ids:
                        state["latest_outcome_task_id"] = outcome_ids[0]
                    elif state["latest_outcome_task_id"] is None:
                        state["latest_outcome_task_id"] = next(
                            (task_id for task_id in task_states if task_states[task_id] in {"succeeded", "failed", "interrupted"}),
                            None,
                        )
                    attention_tasks = sum(1 for task_state in task_states.values() if task_state in {"failed", "interrupted"})
                    state["task_states"] = task_states
                except (OSError, ValueError, urllib.error.URLError):
                    transition["task_outcomes"] = []
                    attention_tasks = int(state["attention_tasks"] or 0)
                try:
                    bridge_status = request_json("/api/codex-bridge/status")
                    bridge_threads = bridge_status.get("threads", [])
                    codex_active = sum(
                        1 for thread in bridge_threads
                        if isinstance(thread, dict) and thread.get("active_turn")
                    )
                    bridge_approvals = bridge_status.get("pending_approvals", [])
                    codex_pending_approvals = sum(
                        1 for approval in bridge_approvals
                        if isinstance(approval, dict) and approval.get("status") == "pending"
                    )
                except (OSError, ValueError, urllib.error.URLError):
                    codex_active = int(state["codex_active"] or 0)
                    codex_pending_approvals = int(state["codex_pending_approvals"] or 0)
                transition["became_ready"] = not state["ready"]
                transition["activity_started"] = previous_active == 0 and active > 0
                transition["activity_stopped"] = bool(previous_active) and active == 0
                transition["approval_required"] = pending_approvals > 0 and previous_pending_approvals in {None, 0}
                approval_status = f" · {pending_approvals} approval required" if pending_approvals else ""
                attention_status = f" · {attention_tasks} task review" if attention_tasks else ""
                codex_activity_status = f" · {codex_active} Codex active" if codex_active else ""
                codex_approval_status = f" · {codex_pending_approvals} Codex approval" if codex_pending_approvals else ""
                state["status"] = f"ready · {active} active · {provider}{approval_status}{attention_status}{codex_activity_status}{codex_approval_status}"
                state["active"] = active
                state["pending_approvals"] = pending_approvals
                state["attention_tasks"] = attention_tasks
                state["codex_active"] = codex_active
                state["codex_pending_approvals"] = codex_pending_approvals
                state["provider"] = provider
                state["ready"] = True
                try:
                    state["muted"] = bool(request_json("/api/harness/voice/status").get("muted", False))
                except (OSError, ValueError, urllib.error.URLError):
                    pass
            except (OSError, ValueError, urllib.error.URLError):
                state["status"] = "starting or unavailable"
            return transition

        def publish_status():
            icon = icon_ref.get("icon")
            if icon is None:
                return
            try:
                icon.title = f"OBus — {state['status']}"
                icon.update_menu()
            except (AttributeError, OSError, RuntimeError):
                pass

        def notify(message: str):
            """Issue an optional native, secret-safe desktop notification."""
            icon = icon_ref.get("icon")
            if icon is None or not getattr(icon, "HAS_NOTIFICATION", False):
                return
            try:
                icon.notify(message, title="OBus")
            except (AttributeError, OSError, RuntimeError):
                pass

        def refresh_and_publish(*, announce: bool):
            transition = refresh_status()
            publish_status()
            if not announce:
                return
            if transition["approval_required"]:
                notify("A major-risk action is waiting for your local approval. Open OBus to review it.")
            elif "interrupted" in transition.get("task_outcomes", []):
                notify("A local task was interrupted. Review its checkpoint before choosing whether to resume it.")
            elif "failed" in transition.get("task_outcomes", []):
                notify("A local task needs review after a failed attempt. Inspect its redacted timeline and checkpoint.")
            elif "succeeded" in transition.get("task_outcomes", []):
                notify("A local task completed. Open OBus to review its redacted result and receipt.")
            elif transition["became_ready"]:
                notify("Local dashboard ready. OBus remains local by default.")
            elif transition["activity_started"]:
                notify("Local agent activity started. Open OBus to follow redacted progress.")
            elif transition["activity_stopped"]:
                notify("Local agent activity stopped. Open OBus to inspect the redacted result.")

        def monitor_status():
            while not monitor_stop.is_set():
                refresh_and_publish(announce=True)
                monitor_stop.wait(TRAY_STATUS_POLL_SECONDS)

        def toggle_mute(icon, _item):
            desired = not bool(state["muted"])
            try:
                state["muted"] = bool(request_json(
                    "/api/harness/voice/mute", "PATCH", {"muted": desired}
                ).get("muted", desired))
            except (OSError, ValueError, urllib.error.URLError):
                state["status"] = "voice control unavailable"
            publish_status()

        def voice_is_muted(_item):
            refresh_status()
            return bool(state["muted"])

        def manual_refresh(_icon, _item):
            refresh_and_publish(announce=True)

        def open_latest_task_outcome(_icon, _item):
            task_id = str(state.get("latest_outcome_task_id") or "")
            if re.fullmatch(r"[A-Za-z0-9-]{1,96}", task_id):
                open_page_action(f"dashboard&task={task_id}")
            else:
                open_page_action("dashboard")

        def exit_from_tray(tray, _item):
            monitor_stop.set()
            exit_action()
            tray.stop()

        icon = pystray.Icon(
            "OBus", _tray_image(), "OBus — starting",
            menu=pystray.Menu(
                pystray.MenuItem(lambda _item: f"OBus — {state['status']}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Open OBus", lambda _icon, _item: open_action(), default=True),
                pystray.MenuItem("Open active agents", lambda _icon, _item: open_page_action("runtime")),
                pystray.MenuItem(
                    lambda _item: f"Review major-risk approvals ({int(state['pending_approvals'] or 0)})",
                    lambda _icon, _item: open_page_action("runtime"),
                ),
                pystray.MenuItem(
                    lambda _item: f"Review task outcomes ({int(state['attention_tasks'] or 0)})",
                    lambda _icon, _item: open_page_action("runtime"),
                ),
                pystray.MenuItem(
                    "Open latest task outcome",
                    open_latest_task_outcome,
                    enabled=lambda _item: bool(state.get("latest_outcome_task_id")),
                ),
                pystray.MenuItem(
                    lambda _item: f"Review Codex approvals ({int(state['codex_pending_approvals'] or 0)})",
                    lambda _icon, _item: open_page_action("home"),
                ),
                pystray.MenuItem("Open run receipts", lambda _icon, _item: open_page_action("runs")),
                pystray.MenuItem("Refresh local status", manual_refresh),
                pystray.MenuItem("Mute voice", toggle_mute, checked=voice_is_muted),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit OBus", exit_from_tray),
            ),
        )
        icon_ref["icon"] = icon
        icon._obus_status_monitor_stop = monitor_stop
        threading.Thread(target=icon.run, name="obus-system-tray", daemon=True).start()
        threading.Thread(target=monitor_status, name="obus-tray-status", daemon=True).start()
        return icon
    except (ImportError, OSError):
        return None


def wait_for_server(url: str, attempts: int = 80, delay: float = 0.02) -> bool:
    """Wait until the canonical local OBus health contract is ready.

    The 20 ms retry cadence keeps startup responsiveness below the requested
    30 ms bound without busy-spinning the launcher.
    """
    for _ in range(attempts):
        if obus_health_state(url) == "ready":
            return True
        time.sleep(delay)
    return False


def open_window_when_ready():
    if wait_for_server(HEALTH_URL):
        opened = open_app_window(APP_URL)
        record_startup_event("fallback_window_opened" if opened else "fallback_window_failed")


def headless_requested(args: list[str] | None = None) -> bool:
    """Return whether this runtime should serve its API without desktop UI."""
    supplied = sys.argv[1:] if args is None else args
    return "--headless" in supplied or "--serve" in supplied


def run_native_desktop_runtime(server) -> None:
    """Own the local server and native window lifecycle for a normal desktop run."""

    record_startup_event("local_server_starting", host="loopback", port=APP_PORT)
    server_thread = threading.Thread(target=server.run, name="obus-local-server", daemon=True)
    server_thread.start()
    if not wait_for_server(HEALTH_URL):
        record_startup_event("local_server_unhealthy", timeout_ms=1600)
        server.should_exit = True
        server_thread.join(timeout=5)
        show_startup_error(
            f"OBus could not start its local dashboard on port {APP_PORT}. "
            "Close any conflicting local service and restart OBus. "
            "A startup diagnostic was saved in the OBus logs."
        )
        return
    record_startup_event("local_server_ready")

    def exit_desktop() -> None:
        server.should_exit = True
        close_native_window(allow_app_exit=True)

    tray = start_system_tray(
        lambda: open_app_window(APP_URL),
        exit_desktop,
        lambda page: open_app_window(desktop_page_url(page)),
    )
    try:
        if run_native_desktop_window(APP_URL, hide_to_tray_on_close=tray is not None):
            # With a tray icon, a normal close hides the native window and keeps
            # pywebview running. Reaching here therefore means explicit Exit OBus.
            server.should_exit = True
        else:
            # Native WebView2 may be unavailable on a machine. Retain the existing
            # browser-window UX without changing any local API authority.
            opened = open_app_window(APP_URL)
            record_startup_event("native_fallback_opened" if opened else "native_fallback_failed")
        server_thread.join()
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)
        if tray:
            stop_system_tray(tray)


def main(args: list[str] | None = None):
    """Start OBus in desktop, MCP, or API-only headless mode."""
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

    args = list(sys.argv[1:] if args is None else args)
    if "--mcp" in args:
        from obus_mcp_server import serve
        serve()
        return
    headless = headless_requested(args)
    record_startup_event("launch_requested", mode="headless" if headless else "desktop")
    print("=" * 50)
    print("OBus MOA Headless Runtime" if headless else "OBus MOA Runtime")
    print("=" * 50)

    if not acquire_single_instance():
        if wait_for_server(HEALTH_URL, attempts=120, delay=0.05):
            if not headless:
                ensure_app_window(APP_URL)
        return
    
    # Desktop launches may reuse an existing local dashboard. Headless/portal
    # launches must not mistake an unrelated service's generic /health route
    # for OBus; the port-scoped mutex above is the ownership check.
    if not headless:
        existing_health = obus_health_state(HEALTH_URL)
        if existing_health == "ready":
            record_startup_event("reusing_ready_local_dashboard")
            ensure_app_window(APP_URL)
            return
        if existing_health == "unexpected":
            record_startup_event("unexpected_port_listener", port=APP_PORT)
            show_startup_error(
                f"Another service is using OBus's local port ({APP_PORT}). "
                "Stop that service or set a different OBus port before restarting."
            )
            return

    print("\nStarting local API server..." if headless else "\nStarting local dashboard server...")
    # Start the server in the foreground so the EXE owns its lifecycle.
    try:
        sys.path.insert(0, str(APP_DIR))
        from backend.main import app
        import uvicorn
        bind_host = os.environ.get("OBUS_HOST", "127.0.0.1").strip() or "127.0.0.1"
        server = uvicorn.Server(uvicorn.Config(app, host=bind_host, port=APP_PORT, log_level="warning", access_log=False))
        if not headless and native_webview_available():
            run_native_desktop_runtime(server)
            return
        if not headless:
            record_startup_event(
                "native_host_unavailable",
                host_mode=os.environ.get("OBUS_DESKTOP_HOST", "native").strip().casefold() or "native",
            )
        tray = None if headless else start_system_tray(
            lambda: open_app_window(APP_URL),
            lambda: setattr(server, "should_exit", True),
            lambda page: open_app_window(desktop_page_url(page)),
        )
        if not headless:
            threading.Thread(target=open_window_when_ready, daemon=True).start()
        server.run()
        if tray:
            stop_system_tray(tray)
    except ImportError as e:
        print("\nError: Could not import backend modules")
        print(f"   {e}")
        print(f"\nPlease ensure all backend files are in place:")
        print(f"   - {APP_DIR}/backend/")
        sys.exit(1)


if __name__ == '__main__':
    main()
