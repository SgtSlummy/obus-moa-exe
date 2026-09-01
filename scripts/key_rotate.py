#!/usr/bin/env python3
"""OBus key rotation script.

This script demonstrates a minimal key‑rotation loop for OBus keys that have an
``expires_at`` timestamp (stored in ISO‑8601 UTC).  It performs three steps for
keys that belong to the current host:

1. Load the list of keys from the local OBus state.  Keys are expected to have an
   ``expires_at`` attribute.  The script ignores any keys that do not have a
   timestamp.

2. For each key whose timestamp is in the past, mark the key as ``staged`` via the
   OBus API, then run a test call.  If the test succeeds the key is marked
   ``ready`` again.  If the test fails a log message is emitted; the key will be
   left in ``staged`` state until the next run.

3. Keys that are already ``ready`` and not expired simply pass through.

The script expects the following environment variables:

- ``OCCULTBUS_BASE_URL`` – base URL of the running OBus instance.
- ``OCCULTBUS_API_KEY``   – shared secret for the OBus API.

When the script runs successfully, it prints a one‑liners log summary.
"""

import os
import json
import datetime
import logging
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Configuration constants – tweak as needed.
BASE_URL = os.environ.get("OCCULTBUS_BASE_URL", "http://127.0.0.1:38174/v1")
API_KEY = os.environ.get("OCCULTBUS_API_KEY", "")
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "OBus-Key-Rotor-1.0",
}
if API_KEY:
    HEADERS["X-OBus-Access"] = API_KEY
else:
    logging.warning("No OCCULTBUS_API_KEY set – proceeding unauthenticated.")

# Simple helper for HTTP requests.

def _req(url, method="GET", data=None):
    req = Request(url, method=method, headers=HEADERS)
    if data is not None:
        req.data = json.dumps(data).encode("utf-8")
        HEADERS["Content-Type"] = "application/json"
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8")) if resp.status == 200 else None
    except HTTPError as e:
        logging.warning("HTTP %s request to %s failed: %s", e.code, url, e.reason)
        return None
    except URLError as e:
        logging.warning("Network error contacting %s: %s", url, e.reason)
        return None

# Load all keys – the OBus dashboard returns only the public view.
# We rely on the underlying JSON file to have the ``expires_at`` field
# for rotation.

def load_keys():
    data = _req(f"{BASE_URL}/api/keys")
    return data or []

# Update key state via API.

def update_key_state(key_id, state):
    return _req(f"{BASE_URL}/api/keys/{key_id}", method="PUT", data={"state": state})

# Test a key – returns bool success.

def test_key(key_id):
    resp = _req(f"{BASE_URL}/api/keys/{key_id}/test", method="POST")
    return resp is not None and resp.get("success", False)

# Main rotation loop.

def rotate_keys():
    keys = load_keys()
    if not keys:
        logging.info("No keys returned from OBus – aborting.")
        return
    now = datetime.datetime.utcnow()
    for key in keys:
        key_id = key.get("id")
        expires = key.get("expires_at")
        if not expires:
            continue
        try:
            exp_ts = datetime.datetime.fromisoformat(expires)
        except ValueError:
            logging.warning("Key %s has malformed expires_at: %s", key_id, expires)
            continue
        if exp_ts <= now:
            logging.info("Key %s expired – moving to staged.", key_id)
            update_key_state(key_id, "staged")
            if test_key(key_id):
                logging.info("Key %s refreshed – set to ready.", key_id)
                update_key_state(key_id, "ready")
            else:
                logging.warning("Key %s test failed after staging. Will retry next cycle.", key_id)
        else:
            logging.debug("Key %s not expired – expiring at %s.", key_id, expires)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    rotate_keys()
