from backend import access_gate


def test_unconfigured_access_gate_rejects_credentials_and_sessions(monkeypatch) -> None:
    monkeypatch.setattr(access_gate, "load_config", lambda: None)

    assert access_gate.verify_password("untrusted-input") is False
    assert access_gate.session_valid(None) is False
    assert access_gate.session_valid("untrusted-input") is False


def test_unconfigured_access_gate_reports_local_status(monkeypatch) -> None:
    monkeypatch.setattr(access_gate, "load_config", lambda: None)

    assert access_gate.status() == {
        "enabled": False,
        "unlocked": True,
        "machine_bound": True,
    }


def test_machine_fingerprint_is_stable_and_nonempty() -> None:
    first = access_gate.machine_fingerprint()

    assert first
    assert first == access_gate.machine_fingerprint()
