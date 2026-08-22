#!/usr/bin/env python3
"""
OBus Launcher - First-run setup detection and dashboard launch
"""
import sys
import os
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
        'completed_at': datetime.now(timezone.utc).isoformat() + 'Z',
        'version': '1.0.0'
    }
    with open(SETUP_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def open_browser(url: str):
    """Open URL in browser"""
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        print(f"Please open: {url}")


def wait_for_server(url: str, attempts: int = 80, delay: float = 0.1) -> bool:
    """Wait until the local HTTP server responds before opening the browser."""
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


def open_browser_when_ready():
    if wait_for_server("http://127.0.0.1:8080/health"):
        open_browser("http://127.0.0.1:8080/?build=obus-modern-11")


def main():
    """Main entry point with first-run logic"""
    print("=" * 50)
    print("OBus MOA Runtime")
    print("=" * 50)
    
    if wait_for_server("http://127.0.0.1:8080/health", attempts=1, delay=0):
        open_browser("http://127.0.0.1:8080/?build=obus-modern-11")
        return

    print("\nStarting local dashboard server...")
    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    # Start the server in the foreground so the EXE owns its lifecycle.
    try:
        sys.path.insert(0, str(APP_DIR))
        from backend.main import app
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning", access_log=False)
    except ImportError as e:
        print("\nError: Could not import backend modules")
        print(f"   {e}")
        print(f"\nPlease ensure all backend files are in place:")
        print(f"   - {APP_DIR}/backend/")
        sys.exit(1)


if __name__ == '__main__':
    main()