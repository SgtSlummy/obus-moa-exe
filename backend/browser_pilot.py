"""Explicit, read-only bridge to an already-installed local PinchTab runtime.

OBus never installs, configures, starts as a daemon, or attaches to a user's daily
browser here.  A local operator chooses a public HTTPS URL in the desktop UI; OBus
then creates an isolated PinchTab session and returns one bounded accessibility
snapshot for review.  Page text is untrusted and this module deliberately exposes
no click, type, cookie, download, upload, evaluation, or credential operations.
"""
from __future__ import annotations

import os
import re
import shutil
import urllib.parse

from backend.process_utils import MAX_SUBPROCESS_OUTPUT_BYTES, run_bounded_subprocess
from backend.secret_safety import redact_text


PINCHTAB_SESSION_PATTERN = re.compile(r"\b(?:ses|session)_[A-Za-z0-9_-]{6,128}\b")
MAX_URL_LENGTH = 2_048
MAX_SNAPSHOT_CHARACTERS = 24_000
_PINCHTAB_TIMEOUT_SECONDS = 20


def _pinchtab_binary() -> str | None:
    """Return an operator-installed executable only; never search or install one."""

    return shutil.which("pinchtab")


def status() -> dict:
    binary = _pinchtab_binary()
    return {
        "available": bool(binary),
        "mode": "explicit-read-only",
        "reason": (
            "PinchTab is available for an explicit, isolated read-only browser observation."
            if binary
            else "Install and configure PinchTab separately to enable the optional browser pilot. OBus will not install it."
        ),
        "limits": [
            "Local desktop operator chooses every URL.",
            "Public HTTPS navigation only; no browser action tools are exposed.",
            "One isolated session per observation; no cookies, credentials, downloads, uploads, or browser state are read.",
        ],
    }


def _public_https_url(value: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > MAX_URL_LENGTH:
        raise ValueError("Enter one public HTTPS URL within 2,048 characters.")
    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("Browser pilot accepts a public HTTPS URL only.")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        raise ValueError("Local or private-network browser targets are not allowed.")
    # Literal IP targets are intentionally excluded. PinchTab receives only a user-selected
    # public hostname and operates in its separately configured, dedicated browser context.
    if re.fullmatch(r"\[?[0-9a-fA-F:.]+\]?", hostname):
        raise ValueError("Use a public HTTPS hostname, not a literal IP address.")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))


def _bounded_output(value: str) -> str:
    text = redact_text(str(value or "")).strip()
    return text[:MAX_SNAPSHOT_CHARACTERS]


def observe(url: str) -> dict:
    """Navigate once in an isolated session and return an accessibility snapshot.

    This is a user-initiated observation, not a general browser tool.  PinchTab's
    command API is invoked directly (never through a shell) and output remains
    bounded/redacted before it returns to the local dashboard.
    """

    target = _public_https_url(url)
    binary = _pinchtab_binary()
    if not binary:
        raise RuntimeError(status()["reason"])
    try:
        created = run_bounded_subprocess(
            [binary, "session", "create", "--agent-id", "obus-readonly"],
            _PINCHTAB_TIMEOUT_SECONDS,
            limit=min(MAX_SUBPROCESS_OUTPUT_BYTES, 128 * 1024),
        )
    except Exception as exc:  # pinchtab may be present but not executable/configured.
        raise RuntimeError(f"Could not create an isolated PinchTab session: {exc}") from exc
    if created.returncode != 0:
        raise RuntimeError(_bounded_output(created.stderr) or "PinchTab could not create an isolated session.")
    match = PINCHTAB_SESSION_PATTERN.search(created.stdout)
    if not match:
        raise RuntimeError("PinchTab returned no isolated session identifier; no browser navigation was started.")
    environment = os.environ.copy()
    environment["PINCHTAB_SESSION"] = match.group(0)
    try:
        result = run_bounded_subprocess(
            [binary, "nav", target, "--snap", "--block-images", "--timeout", "15"],
            _PINCHTAB_TIMEOUT_SECONDS,
            env=environment,
            limit=min(MAX_SUBPROCESS_OUTPUT_BYTES, 512 * 1024),
        )
    except Exception as exc:
        raise RuntimeError(f"Browser observation ended before a snapshot was available: {exc}") from exc
    if result.returncode != 0:
        raise RuntimeError(_bounded_output(result.stderr) or "PinchTab could not observe the selected page.")
    snapshot = _bounded_output(result.stdout)
    if not snapshot:
        raise RuntimeError("PinchTab returned an empty snapshot; no page content was added to OBus.")
    return {
        "url": target,
        "mode": "explicit-read-only",
        "persistence": "none",
        "snapshot": snapshot,
        "notice": "Untrusted page data shown for review only. OBus did not click, type, read browser state, or grant an agent browser authority.",
    }
