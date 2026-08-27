"""Shared safe Codex CLI policy for unattended OBus execution.

OBus is intentionally autonomous for ordinary workspace work.  It delegates
command review to Codex's current ``--approve-for-me`` mode, which pairs
on-request approvals with the workspace-write sandbox.  Full-access/yolo flags
must never be introduced in an OBus command builder.
"""
from __future__ import annotations

from pathlib import Path


FORBIDDEN_CODEX_FLAGS = frozenset(
    {
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--yolo",
    }
)


def build_codex_exec_command(
    executable: str,
    prompt: str,
    *,
    model: str | None = None,
    output_path: Path | None = None,
) -> list[str]:
    """Build the one allowed unattended Codex command shape.

    ``--approve-for-me`` is an upstream Codex contract that configures
    automatic approval review, ``approval_policy=on-request``, and the
    ``workspace-write`` sandbox.  OBus never falls back to an unrestricted
    execution flag.
    """

    command = [
        executable,
        "exec",
        "--skip-git-repo-check",
        "--approve-for-me",
        "--color",
        "never",
    ]
    if output_path is not None:
        command.extend(["--output-last-message", str(output_path)])
    if model:
        command.extend(["-m", model])
    command.append(prompt)
    if FORBIDDEN_CODEX_FLAGS.intersection(command):
        raise ValueError("unsafe Codex execution flag")
    return command

