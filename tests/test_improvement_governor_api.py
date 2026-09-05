from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend import improvement_governor_api as api
from backend.improvement_governor import JournalIntegrityError


class FakeGovernor:
    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        self.loop_count = 0
        self.active_loop: dict[str, Any] | None = None
        self.latest_loop: dict[str, Any] | None = None
        self.start_calls = 0

    def status(self) -> dict[str, Any]:
        state = (
            self.active_loop or self.latest_loop or {"stage": "idle"}
        ).get("stage", "idle")
        return {
            "state": state,
            "active_loop": self.active_loop,
            "latest_loop": self.latest_loop,
            "journal": {
                "verified": True,
                "integrity": "verified",
                "loop_count": self.loop_count,
            },
            "next_action": "start_loop" if self.active_loop is None else "none",
            "human_authorization_required": True,
            "autonomous_promotion_permitted": False,
            "promotion_authorized": False,
        }

    def start_loop(self) -> dict[str, Any]:
        self.start_calls += 1
        if self.active_loop is None:
            self.loop_count += 1
            self.active_loop = {
                "loop_id": f"loop-{self.loop_count}",
                "stage": "sandboxed",
            }
            self.latest_loop = self.active_loop
        return self.status()

    def finish_active_loop(self) -> None:
        assert self.active_loop is not None
        self.latest_loop = {**self.active_loop, "stage": "rolled_back"}
        self.active_loop = None


def _json(response: Any) -> dict[str, Any]:
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (JournalIntegrityError("journal chain mismatch"), "journal chain mismatch"),
        (OSError("C:/private/path denied"), "improvement journal path is unavailable"),
    ],
)
def test_dependency_construction_failure_returns_integrity_envelope(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_message: str,
) -> None:
    def fail() -> None:
        raise error

    monkeypatch.setattr(api, "_cached_improvement_governor", fail)

    dependency = api.get_improvement_governor()
    response = api.governor_status(dependency)
    payload = _json(response)

    assert response.status_code == 409
    assert payload["state"] == "integrity_error"
    assert payload["journal"]["verified"] is False
    assert payload["journal"]["error"] == expected_message
    assert payload["autonomous_promotion_permitted"] is False


def test_start_idempotency_key_survives_terminal_transition(tmp_path: Path) -> None:
    governor = FakeGovernor(tmp_path / "governor.sqlite3")

    first = api.start_improvement_loop(governor, {}, "request-1")
    assert first.status_code == 200
    assert first.headers["Idempotency-Replayed"] == "false"
    assert governor.start_calls == 1

    governor.finish_active_loop()
    replay = api.start_improvement_loop(governor, {}, "request-1")

    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert _json(replay)["state"] == "rolled_back"
    assert governor.start_calls == 1
    assert (tmp_path / "governor.sqlite3.idempotency.sqlite3").exists()


def test_start_rejects_conflicting_header_and_body_keys(tmp_path: Path) -> None:
    governor = FakeGovernor(tmp_path / "governor.sqlite3")

    response = api.start_improvement_loop(
        governor,
        {"idempotency_key": "body-key"},
        "header-key",
    )
    payload = _json(response)

    assert response.status_code == 409
    assert payload["error"]["code"] == "idempotency_conflict"
    assert governor.start_calls == 0


def test_start_accepts_body_idempotency_key(tmp_path: Path) -> None:
    governor = FakeGovernor(tmp_path / "governor.sqlite3")

    response = api.start_improvement_loop(
        governor,
        {"idempotency_key": "body-key"},
        None,
    )

    assert response.status_code == 200
    assert response.headers["Idempotency-Key"] == "body-key"
    assert governor.start_calls == 1
