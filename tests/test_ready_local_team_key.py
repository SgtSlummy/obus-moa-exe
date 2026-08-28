from unittest.mock import patch

from backend.main import _ready_local_team_key


def _state(keys, selected_model="gpt-oss:20b"):
    return {"keys": keys, "settings": {"selected_model": selected_model}}


def test_ready_local_team_key_uses_verified_local_fallback_when_status_probe_lags():
    state = _state([
        {
            "id": "key-local-ollama",
            "local": True,
            "state": "ready",
            "verified": True,
            "model": "gpt-oss:20b",
        }
    ])

    with patch("backend.main.provider_statuses", return_value=[
        {"id": "key-local-ollama", "connected": False}
    ]):
        chosen = _ready_local_team_key(state)

    assert chosen["id"] == "key-local-ollama"


def test_ready_local_team_key_never_falls_back_to_remote_or_unverified_key():
    state = _state([
        {"id": "key-remote", "local": False, "state": "ready", "verified": True},
        {"id": "key-local-unverified", "local": True, "state": "ready", "verified": False},
    ])

    with patch("backend.main.provider_statuses", return_value=[]):
        try:
            _ready_local_team_key(state)
        except Exception as error:
            assert getattr(error, "status_code", None) == 409
        else:
            raise AssertionError("expected a verified local-key requirement")
