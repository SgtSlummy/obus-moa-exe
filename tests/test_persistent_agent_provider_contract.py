from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import persistent_agents


def test_provider_url_validation_narrows_and_normalizes_hostname():
    assert (
        persistent_agents._validated_provider_base_url(
            "codex", "https://API.OPENAI.COM/v1/"
        )
        == "https://API.OPENAI.COM/v1"
    )
    with pytest.raises(RuntimeError, match="approved secret-free endpoint"):
        persistent_agents._validated_provider_base_url("codex", None)


def test_codex_output_bytes_are_decoded_to_text(monkeypatch, tmp_path: Path):
    def fake_run(command, timeout, cwd):
        output_flag = command.index("--output-last-message")
        Path(command[output_flag + 1]).write_bytes("Codex ready ✓".encode("utf-8"))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(persistent_agents, "run_bounded_subprocess", fake_run)

    output = persistent_agents.execute_codex_prompt(
        lambda *args: ["codex", *args],
        {"model": "gpt-5.6-luna"},
        "verify",
        tmp_path,
    )

    assert output == "Codex ready ✓"
