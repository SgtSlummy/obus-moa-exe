"""Machine-local password gate for packaged OBus deployments."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

_ACCESS_LOCK = threading.RLock()
_SESSIONS: dict[str, float] = {}
_SESSION_SECONDS = 12 * 60 * 60
_FAILED_ATTEMPTS = 0
_BLOCKED_UNTIL = 0.0
_MAX_FAILED_ATTEMPTS = 5
_BACKOFF_SECONDS = 15.0


def config_path() -> Path | None:
    value = os.environ.get("OBUS_ACCESS_CONFIG", "").strip()
    return Path(value) if value else None


def machine_fingerprint() -> str:
    """Return a non-reversible local machine binding, with a Windows primary path."""
    source = ""
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                source = str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except OSError:
            pass
    if not source:
        source = os.environ.get("COMPUTERNAME") or os.uname().nodename
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_config() -> dict | None:
    path = config_path()
    if not path or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not value:
            return {"_invalid": True}
        return value
    except (OSError, ValueError):
        return {"_invalid": True}


def status() -> dict:
    config = load_config()
    if not config:
        return {"enabled": False, "unlocked": True, "machine_bound": True}
    expected = str(config.get("machine_binding") or "")
    bound = bool(expected and secrets.compare_digest(expected, machine_fingerprint()))
    return {
        "enabled": True,
        "unlocked": False,
        "machine_bound": bound,
        "role": config.get("role"),
        "label": config.get("label"),
    }


def verify_password(password: str) -> bool:
    global _FAILED_ATTEMPTS, _BLOCKED_UNTIL
    now = time.time()
    with _ACCESS_LOCK:
        if now < _BLOCKED_UNTIL:
            return False
    config = load_config()
    if not config or not status()["machine_bound"]:
        return False
    try:
        iterations = int(config["iterations"])
        salt = base64.b64decode(config["salt"], validate=True)
        expected = base64.b64decode(config["password_hash"], validate=True)
    except (KeyError, TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    valid = secrets.compare_digest(actual, expected)
    with _ACCESS_LOCK:
        if valid:
            _FAILED_ATTEMPTS = 0
            _BLOCKED_UNTIL = 0.0
        else:
            _FAILED_ATTEMPTS += 1
            if _FAILED_ATTEMPTS >= _MAX_FAILED_ATTEMPTS:
                _BLOCKED_UNTIL = time.time() + _BACKOFF_SECONDS
                _FAILED_ATTEMPTS = 0
    return valid


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with _ACCESS_LOCK:
        _SESSIONS[token] = time.time() + _SESSION_SECONDS
    return token


def session_valid(token: str | None) -> bool:
    if not token:
        return False
    with _ACCESS_LOCK:
        expiry = _SESSIONS.get(token)
        if not expiry or expiry <= time.time():
            _SESSIONS.pop(token, None)
            return False
        return True
