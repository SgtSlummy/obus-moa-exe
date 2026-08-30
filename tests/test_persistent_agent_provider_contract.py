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


def test_omniroute_is_limited_to_its_local_openai_compatible_gateway():
    assert (
        persistent_agents._validated_provider_base_url(
            "omniroute", "http://127.0.0.1:20128/v1/"
        )
        == "http://127.0.0.1:20128/v1"
    )
    with pytest.raises(RuntimeError, match="approved secret-free endpoint"):
        persistent_agents._validated_provider_base_url(
            "omniroute", "https://omniroute.online/v1"
        )


def test_omniroute_executes_without_a_local_credential_reference(monkeypatch):
    captured = {}

    def fake_http(url, headers, payload):
        captured.update(url=url, headers=headers, payload=payload)
        return {"choices": [{"message": {"content": "routed"}}]}

    monkeypatch.setattr(persistent_agents, "_http_json", fake_http)
    assert persistent_agents.execute_remote_provider(
        {"provider": "omniroute", "model": "auto", "base_url": "http://127.0.0.1:20128/v1"},
        "route this",
    ) == "routed"
    assert captured["url"] == "http://127.0.0.1:20128/v1/chat/completions"
    assert captured["headers"] == {}


def test_omniroute_catalog_provider_id_is_safe_and_bounded():
    from backend.main import _omniroute_catalog_id

    assert _omniroute_catalog_id("OpenAI / GPT-5") == "openai-gpt-5"
    assert _omniroute_catalog_id("@@@") == ""
    assert len(_omniroute_catalog_id("a" * 100)) == 80


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
