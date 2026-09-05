from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi.responses import JSONResponse

from backend import improvement_candidate
from backend.improvement_governor import InvalidTransitionError
from backend.improvement_governor_api import screen_improvement_loop


class _FakeGovernor:
    def __init__(self, journal_path: Path) -> None:
        self.journal_path = journal_path
        self.run_loop = {
            "loop_id": "loop-1",
            "stage": "sandboxed",
            "candidate": {"digest": "sha256:candidate"},
        }
        self.screen_calls = 0
        self.status_calls = 0
        self.race_on_status_call: int | None = None
        self.screen_error: Exception | None = None

    def status(self) -> dict[str, Any]:
        self.status_calls += 1
        if self.race_on_status_call == self.status_calls:
            self.run_loop["stage"] = "rejected"
        loop = deepcopy(self.run_loop)
        return {
            "active_loop": loop,
            "latest_loop": deepcopy(loop),
            "journal": {"verified": True, "loop_count": 1},
        }

    def screen(self, loop_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
        assert loop_id == self.run_loop["loop_id"]
        assert receipt == {"trusted": True}
        self.screen_calls += 1
        if self.screen_error is not None:
            raise self.screen_error
        self.run_loop["stage"] = "awaiting_authorization"
        self.run_loop["screening"] = {
            "receipt_digest": "sha256:" + "a" * 64,
            "attestation_digest": "sha256:" + "b" * 64,
            "evidence_summary": {
                "probe_runs": 3,
                "probe_passes": 3,
                "sandbox_kind": "docker",
            },
        }
        return self.status()


def _decoded(response: Any) -> tuple[int, dict[str, Any]]:
    if isinstance(response, JSONResponse):
        return response.status_code, json.loads(response.body)
    return 200, response


def _successful_candidate(candidate_kind: str, *, loop: dict[str, Any]) -> dict[str, Any]:
    assert candidate_kind == improvement_candidate.CANDIDATE_KIND
    assert loop["stage"] == "sandboxed"
    return {
        "candidate_kind": candidate_kind,
        "receipt": {"trusted": True},
        "receipt_digest": "sha256:" + "a" * 64,
        "attestation_digest": "sha256:" + "b" * 64,
        "evidence_summary": {"probe_runs": 3, "probe_passes": 3},
    }


def test_duplicate_candidate_screen_replays_persisted_evidence_without_rerun(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    governor = _FakeGovernor(tmp_path / "improvement.jsonl")
    runner_calls = 0

    def runner(candidate_kind: str, *, loop: dict[str, Any]) -> dict[str, Any]:
        nonlocal runner_calls
        runner_calls += 1
        return _successful_candidate(candidate_kind, loop=loop)

    monkeypatch.setattr(improvement_candidate, "run_improvement_candidate", runner)

    first = screen_improvement_loop("loop-1", governor, {})
    governor.run_loop["stage"] = "rejected"
    second = screen_improvement_loop("loop-1", governor, {})
    first_status, first_body = _decoded(first)
    second_status, second_body = _decoded(second)

    assert first_status == second_status == 200
    assert runner_calls == governor.screen_calls == 1
    assert first_body["candidate_run"] == second_body["candidate_run"]
    assert second_body["candidate_run"]["evidence_summary"]["probe_passes"] == 3
    assert isinstance(second, JSONResponse)
    assert second.headers["Idempotency-Replayed"] == "true"


def test_candidate_infrastructure_failure_is_retryable_without_transition(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    governor = _FakeGovernor(tmp_path / "improvement.jsonl")
    runner_calls = 0

    def runner(candidate_kind: str, *, loop: dict[str, Any]) -> dict[str, Any]:
        nonlocal runner_calls
        runner_calls += 1
        if runner_calls == 1:
            raise improvement_candidate.CandidateRunError("docker unavailable")
        return _successful_candidate(candidate_kind, loop=loop)

    monkeypatch.setattr(improvement_candidate, "run_improvement_candidate", runner)

    failed = screen_improvement_loop("loop-1", governor, {})
    cached = screen_improvement_loop("loop-1", governor, {})
    retried = screen_improvement_loop("loop-1", governor, {"retry_key": "operator-retry-1"})
    failed_status, failed_body = _decoded(failed)
    cached_status, cached_body = _decoded(cached)
    retried_status, retried_body = _decoded(retried)

    assert failed_status == cached_status == 503
    assert failed_body["retryable"] is cached_body["retryable"] is True
    assert isinstance(failed_body["retry_key"], str) and failed_body["retry_key"]
    assert isinstance(cached_body["retry_key"], str) and cached_body["retry_key"]
    assert failed_body["active_loop"]["stage"] == "sandboxed"
    assert cached_body["active_loop"]["stage"] == "sandboxed"
    assert runner_calls == 2
    assert governor.screen_calls == 1
    assert retried_status == 200
    assert retried_body["active_loop"]["stage"] == "awaiting_authorization"

    invalid_retry = screen_improvement_loop("loop-1", governor, {"retry_key": 7})
    invalid_status, invalid_body = _decoded(invalid_retry)
    assert invalid_status == 422
    assert invalid_body["retryable"] is False
    assert "retry_key" not in invalid_body

    unsupported = screen_improvement_loop(
        "loop-1", governor, {"candidate_kind": "client-controlled"}
    )
    unsupported_status, unsupported_body = _decoded(unsupported)
    assert unsupported_status == 422
    assert unsupported_body["retryable"] is False
    assert "retry_key" not in unsupported_body


def test_stage_race_persists_and_replays_as_retryable_503(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    governor = _FakeGovernor(tmp_path / "improvement.jsonl")
    governor.race_on_status_call = 2
    runner_calls = 0

    def runner(candidate_kind: str, *, loop: dict[str, Any]) -> dict[str, Any]:
        nonlocal runner_calls
        runner_calls += 1
        return _successful_candidate(candidate_kind, loop=loop)

    monkeypatch.setattr(improvement_candidate, "run_improvement_candidate", runner)

    raced = screen_improvement_loop("loop-1", governor, {})
    replayed = screen_improvement_loop("loop-1", governor, {})
    raced_status, raced_body = _decoded(raced)
    replayed_status, replayed_body = _decoded(replayed)

    assert raced_status == replayed_status == 503
    assert raced_body["retryable"] is replayed_body["retryable"] is True
    assert raced_body["retry_key"] and replayed_body["retry_key"]
    assert runner_calls == governor.screen_calls == 0


def test_governor_contract_error_persists_as_terminal_nonretryable(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    governor = _FakeGovernor(tmp_path / "improvement.jsonl")
    governor.screen_error = InvalidTransitionError("candidate contract changed")
    runner_calls = 0

    def runner(candidate_kind: str, *, loop: dict[str, Any]) -> dict[str, Any]:
        nonlocal runner_calls
        runner_calls += 1
        return _successful_candidate(candidate_kind, loop=loop)

    monkeypatch.setattr(improvement_candidate, "run_improvement_candidate", runner)

    failed = screen_improvement_loop("loop-1", governor, {})
    replayed = screen_improvement_loop("loop-1", governor, {})
    failed_status, failed_body = _decoded(failed)
    replayed_status, replayed_body = _decoded(replayed)

    assert failed_status == replayed_status == 409
    assert failed_body["retryable"] is replayed_body["retryable"] is False
    assert "retry_key" not in failed_body
    assert "retry_key" not in replayed_body
    assert runner_calls == governor.screen_calls == 1
