#!/usr/bin/env bash
# A one-shot script to apply the patches and restart OBus

set -euo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# 1. Ensure backend/main.py has watchdog start
patch -p0 <<'PATCH'
*** Begin Patch
*** Update File: backend/main.py
@@
     app.include_router(flow_studio_api_router)
     app.include_router(flow_studio_page_router)
+    # start watchdog on boot
+    from .watcher import start_watchdog
+    start_watchdog()
*** End Patch
PATCH

# 2. Ensure backend/keys_api.py test endpoint includes empty prompt
patch -p0 <<'PATCH'
*** Begin Patch
*** Update File: backend/keys_api.py
@@
 @app.post("/api/keys/{key_id}/test")
 def test_key(key_id: str, body: dict):
-    # body already contains "model" and "base_url". Add empty prompt
-    body.setdefault("prompt", "")
+    # Body may omit prompt.  Insert empty string to satisfy older tests.
+    body.setdefault("prompt", "")
*** End Patch
PATCH

# 3. Add or create backend/watcher.py with the loop
cat > backend/watcher.py <<'PY'
#!/usr/bin/env python3
import os, time, logging, threading
from datetime import datetime
from backend import load_state, save_state, get_ollama_status, probe_key_live

log = logging.getLogger("watchdog")
handler = logging.FileHandler(os.path.expanduser("~/.occultbus/watchdog.log"))
handler.setLevel(logging.INFO)
log.addHandler(handler)


def watchdog_loop():
    while True:
        try:
            state = load_state()
            for key in state.get("keys", []):
                if key.get("state") != "ready":
                    continue
                status = get_ollama_status()
                if not status.get("connected"):
                    key["state"] = "staged"
                    key["last_probe_message"] = "runtime offline"
                    continue
                if key.get("model") not in status.get("models", []):
                    key["state"] = "staged"
                    key["last_probe_message"] = "model missing"
                    continue
                if not key.get("local"):
                    res = probe_key_live(key)
                    if not res.get("success"):
                        key["state"] = "staged"
                        key["last_probe_message"] = res.get("reason")
                if key.get("expires_at"):
                    try:
                        exp_ts = datetime.fromisoformat(key["expires_at"])
                        if exp_ts <= datetime.utcnow():
                            key["state"] = "staged"
                            key["last_probe_message"] = "expired"
                    except Exception:
                        pass
            save_state(state)
        except Exception as exc:
            log.exception("watchdog loop failed")
        time.sleep(300)


def start_watchdog():
    thr = threading.Thread(target=watchdog_loop, daemon=True)
    thr.start()

if __name__ == "__main__":
    start_watchdog()
    while True:
        time.sleep(1)
PY

# 4. Restart OBus (kill any running uvicorn instance and launch new one)
pkill -f "uvicorn.*backend.main" || true
exec python -m uvicorn backend.main:app --host 127.0.0.1 --port 38174
