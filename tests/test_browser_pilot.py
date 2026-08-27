import subprocess
from unittest.mock import patch

import pytest

from backend import browser_pilot


def test_browser_pilot_status_never_claims_it_installs_or_controls_a_personal_browser():
    with patch.object(browser_pilot, "_pinchtab_binary", return_value=None):
        status = browser_pilot.status()

    assert status["available"] is False
    assert status["mode"] == "explicit-read-only"
    assert "not install" in status["reason"].lower()
    assert any("credentials" in limit.lower() for limit in status["limits"])


@pytest.mark.parametrize("url", ["http://example.com", "https://localhost/", "https://127.0.0.1/", "https://user:pass@example.com/"])
def test_browser_pilot_rejects_nonpublic_or_credential_urls(url):
    with pytest.raises(ValueError):
        browser_pilot._public_https_url(url)


def test_browser_pilot_uses_an_isolated_session_and_returns_bounded_redacted_snapshot():
    created = subprocess.CompletedProcess(["pinchtab"], 0, "ses_obusabc123", "")
    observed = subprocess.CompletedProcess(["pinchtab"], 0, "e1:link Example\napi_key=secret-value", "")
    with patch.object(browser_pilot, "_pinchtab_binary", return_value="pinchtab"), patch.object(
        browser_pilot, "run_bounded_subprocess", side_effect=[created, observed]
    ) as run:
        result = browser_pilot.observe("https://example.com/docs#ignored")

    assert result["url"] == "https://example.com/docs"
    assert result["mode"] == "explicit-read-only"
    assert result["persistence"] == "none"
    assert "secret-value" not in result["snapshot"]
    assert "e1:link Example" in result["snapshot"]
    assert run.call_args_list[0].args[0] == ["pinchtab", "session", "create", "--agent-id", "obus-readonly"]
    assert run.call_args_list[1].args[0] == ["pinchtab", "nav", "https://example.com/docs", "--snap", "--block-images", "--timeout", "15"]
    assert run.call_args_list[1].kwargs["env"]["PINCHTAB_SESSION"] == "ses_obusabc123"
