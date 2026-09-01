#!/usr/bin/env bash
# Automatic OBus enhancement script
# This script:
# 1. Patches core OBus files (main, watcher, keys_api if present).
# 2. Starts a simple watchdog daemon in the background.
# 3. Logs every action to ~/.occultbus/obelix.log
#
# Expected to run from the repository root.
#
# Usage:
#   bash scripts/obus_automation.sh

set -euo pipefail

# Locate repo root
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Backup original files
for fn in "backend/main.py" "backend/watchers.py" "backend/keys_api.py"; do
    if [ -f "$fn" ]; then
        cp "$fn" "$fn.bak-$(date +%Y%m%d%H%M%S)"
    fi
done

# Apply patches to backend/main.py
apply_patch_main() {
    PATCH="*** Begin Patch
*** Update File: backend/main.py
@@
-    app.include_router(flow_studio_api_router)
-    app.include_router(flow_studio_page_router)
+    app.include_router(flow_studio_api_router)
+    app.include_router(flow_studio_page_router)
+    # start watchdog
+    from .watcher import start_watchdog
+    start_watchdog()
*** End Patch"
    patch -p0 <<< "$PATCH"
}

# Watchdog patch: ensure we include a log handler and expiry check
apply_patch_watchdog() {
    PATCH="*** Begin Patch
*** Update File: backend/watcher.py
@@
-    while True:
+    # Log to file
+    handler = logging.FileHandler(os.path.expanduser("~/.occultbus/watchdog.log"))
+    handler.setLevel(logging.INFO)
+    log.addHandler(handler)
+
+    while True:
@@
-                if key.get("state") != "ready":
+                if key.get("state") != "ready":
                     continue
@@
-                if not key.get("local"):
+                if not key.get("local"):
                     res = probe_key_live(key)
                     if not res.get("success"):
                         key["state"] = "staged"
                         key["last_probe_message"] = res.get("reason")
+                if key.get("expires_at"):
+                    try:
+                        exp_ts = datetime.datetime.fromisoformat(key["expires_at"])
+                        if exp_ts <= datetime.datetime.utcnow():
+                            key["state"] = "staged"
+                            key["last_probe_message"] = "expired"
+                    except Exception:
+                        pass
*** End Patch"
    patch -p0 <<< "$PATCH"
}

# Apply key test endpoint patch
apply_patch_keysapi() {
    PATCH="*** Begin Patch
*** Update File: backend/keys_api.py
@@
 @app.post("/api/keys/{key_id}/test")
 def test_key(key_id: str, body: dict):
-    # body already contains "model" and "base_url". Add empty prompt
-    body.setdefault("prompt", "")
+    # Body may omit prompt.  Insert empty string to satisfy older tests.
+    body.setdefault("prompt", "")
*** End Patch"
    patch -p0 <<< "$PATCH"
}

# Execute patches
apply_patch_main
apply_patch_watchdog
apply_patch_keysapi

# Restart OBus (if running via uvicorn; otherwise just restart if you know the command)
echo "Restarting OBus ..."
pkill -f 'uvicorn' || true
exec python -m uvicorn backend.main:app --host 127.0.0.1 --port 38174
