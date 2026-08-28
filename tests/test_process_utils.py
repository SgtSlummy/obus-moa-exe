from __future__ import annotations

import os

from backend.process_utils import _normalize_windows_command


def test_windows_batch_launcher_is_routed_through_cmd_without_flattening_argv():
    command = [r"C:\\tools\\codex.CMD", "exec", "safe workspace inspection"]

    normalized = _normalize_windows_command(command)

    if os.name == "nt":
        assert normalized[:4] == [os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c"]
        assert "codex.CMD" in normalized[4]
        assert "safe workspace inspection" in normalized[4]
    else:
        assert normalized == command


def test_non_batch_commands_keep_structured_argv():
    command = ["python", "-c", "print('ok')"]

    assert _normalize_windows_command(command) == command
