"""Optional AGPL Warp terminal companion discovery and launch boundary.

OBus remains a local FastAPI application. This module does not embed Warp's Rust
UI into the Python executable; it discovers an explicitly vendored Warp source
checkout and can launch a separately built Warp TUI companion on user request.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WARP_ROOT = PROJECT_ROOT / "third_party" / "warpdotdev-warp"


def warp_root() -> Path:
    configured = os.environ.get("OBUS_WARP_COMPANION_ROOT")
    if configured:
        return Path(configured).expanduser()
    if getattr(sys, "frozen", False):
        adjacent_source = Path(sys.executable).resolve().parent.parent / "third_party" / "warpdotdev-warp"
        if adjacent_source.is_dir():
            return adjacent_source
    return DEFAULT_WARP_ROOT


def warp_binary(root: Path) -> Path:
    configured = os.environ.get("OBUS_WARP_TUI_BIN")
    if configured:
        return Path(configured).expanduser()
    suffix = ".exe" if os.name == "nt" else ""
    return root / "target" / "release" / f"warp-tui-oss{suffix}"


def _source_revision(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, timeout=3, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def status() -> dict[str, Any]:
    root = warp_root()
    required = (root / "Cargo.toml", root / "LICENSE-AGPL", root / "crates" / "warp_tui" / "Cargo.toml")
    source_available = all(path.is_file() for path in required)
    binary = warp_binary(root)
    return {
        "source_available": source_available,
        "tui_available": binary.is_file(),
        "source_revision": _source_revision(root) if source_available else None,
        "license": "AGPL-3.0-only",
        "source_url": "https://github.com/warpdotdev/warp",
        "launch_ready": source_available and binary.is_file(),
        "integration_mode": "optional-local-companion",
    }


def launch() -> dict[str, Any]:
    current = status()
    if not current["launch_ready"]:
        return {
            **current,
            "started": False,
            "message": "Warp source is present, but the optional warp-tui-oss companion has not been built.",
        }
    binary = warp_binary(warp_root())
    options: dict[str, Any] = {"cwd": str(warp_root()), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([str(binary)], **options)
    return {**current, "started": True, "message": "Warp TUI companion launched in its own terminal window."}
