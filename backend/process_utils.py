"""Windows-safe subprocess options for the silent OBus desktop runtime."""
from __future__ import annotations

import os
import subprocess
from typing import Any


def silent_process_kwargs() -> dict[str, Any]:
    """Hide child console windows on Windows while preserving captured output."""
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }
