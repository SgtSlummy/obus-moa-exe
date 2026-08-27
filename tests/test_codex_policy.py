from pathlib import Path

from backend.codex_policy import FORBIDDEN_CODEX_FLAGS, build_codex_exec_command
from backend.execution_policy import classify_major_risk


def test_codex_autonomy_uses_upstream_auto_review_and_workspace_sandbox_contract(tmp_path: Path):
    command = build_codex_exec_command(
        "codex",
        "repair and verify",
        model="gpt-test",
        output_path=tmp_path / "last.txt",
    )

    assert command[:3] == ["codex", "exec", "--skip-git-repo-check"]
    assert "--approve-for-me" in command
    assert "--output-last-message" in command
    assert command[-1] == "repair and verify"
    assert not FORBIDDEN_CODEX_FLAGS.intersection(command)


def test_major_destructive_and_hardware_requests_require_explicit_local_approval():
    assert "bulk_or_irrecoverable_deletion" in classify_major_risk(
        "recursively delete the entire backup history"
    )
    assert "boot_firmware_or_disk_layout" in classify_major_risk("flash the BIOS firmware")
    assert "hardware_safety_controls" in classify_major_risk("raise the GPU power limit")
    assert "hardware_safety_controls" in classify_major_risk("nvidia-smi --power-limit=400")
    assert classify_major_risk("refactor the terminal module and run its tests") == []
