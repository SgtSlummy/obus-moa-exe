from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

from backend.improvement_governor import (
    ImprovementGovernor,
    JournalIntegrityError,
    _authorization_mac,
    _event_hash,
    canonical_json,
)


def _baseline() -> dict[str, Any]:
    return {
        "status": "measured",
        "report_digest": "a" * 64,
        "metrics": {
            "reliability": {"value": 0.55, "target": 0.99, "direction": "maximize"},
            "task_success": {"value": 0.80, "target": 0.95, "direction": "maximize"},
        },
        "comparison": {
            "learning_objective": {
                "task_selection_permitted": True,
                "candidate_selection": {
                    "candidate_kind": "ollama-warm-residency-v1",
                    "objective": {
                        "path": "Qwen warm-runtime reliability acceptance contract",
                        "direction": "verified context",
                        "target": 65_536,
                        "metric": "model context tokens",
                    },
                },
            },
        },
    }


def _governor(
    journal_path: Path,
    *,
    evaluation: dict[str, Any] | None = None,
    authorization_key: bytes | None = None,
) -> ImprovementGovernor:
    return ImprovementGovernor(
        journal_path,
        status_provider=_baseline,
        receipt_evaluator=lambda _receipt: evaluation
        or {"overall_status": "incomplete", "complete": False},
        authorization_key=authorization_key,
    )


def _append_event(
    connection: sqlite3.Connection,
    *,
    loop_id: str,
    event_index: int,
    event_type: str,
    payload: dict[str, Any],
    previous_hash: str,
) -> str:
    event_hash = _event_hash(
        loop_id=loop_id,
        event_index=event_index,
        event_type=event_type,
        payload=payload,
        previous_hash=previous_hash,
    )
    connection.execute(
        """
        INSERT INTO improvement_events(
            loop_id, event_index, event_type, payload_json, previous_hash, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            loop_id,
            event_index,
            event_type,
            canonical_json(payload),
            previous_hash,
            event_hash,
        ),
    )
    return event_hash


def _authorized_payload(
    key: bytes,
    *,
    loop_id: str,
    event_index: int,
    event_type: str,
    previous_hash: str,
    authorization_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "human_authorization": {
            "kind": "human",
            "authorization_id": authorization_id,
            "authorized_by": "test-operator",
        }
    }
    payload["human_authorization"]["mac"] = _authorization_mac(
        key,
        loop_id=loop_id,
        event_index=event_index,
        event_type=event_type,
        payload=payload,
        previous_hash=previous_hash,
    )
    return payload


def _bound_receipt(started: dict) -> dict:
    loop = started["active_loop"]
    binding = {
        "proposal_id": loop["loop_id"],
        "baseline_digest": loop["baseline_digest"],
        "baseline_source_revision": loop["candidate_lineage"]["baseline_source_revision"],
        "baseline_artifact_digest": loop["candidate_lineage"]["baseline_artifact_digest"],
        "candidate_digest": loop["candidate_lineage"]["candidate_digest"],
    }
    objective = loop["objective"]
    candidate_record = {
        **binding,
        "evidence_contract_version": 2,
        "candidate_kind": "ollama-warm-residency-v1",
        "objective": objective,
        "artifact_path": "backend/main.py",
        "source_digest": binding["candidate_digest"],
    }
    return {
        "candidate": candidate_record,
        "_obus_candidate": {
            "binding": binding,
            "candidate_kind": "ollama-warm-residency-v1",
            "evidence_summary": {
                "evidence_contract_version": 2,
                "candidate_kind": "ollama-warm-residency-v1",
                "objective": objective,
                "artifact_path": "backend/main.py",
                "baseline_source_revision": binding["baseline_source_revision"],
                "baseline_artifact_digest": binding["baseline_artifact_digest"],
                "candidate_digest": binding["candidate_digest"],
                "source_digest": binding["candidate_digest"],
            },
            "attestation": {"attestation_digest": "c" * 64},
        },
    }


def test_start_is_deterministic_idempotent_and_chain_is_valid(tmp_path: Path) -> None:
    first_governor = _governor(tmp_path / "first.sqlite3")
    first = first_governor.start_loop()
    repeated = first_governor.start_loop()
    second_fresh = _governor(tmp_path / "second.sqlite3").start_loop()

    assert repeated["active_loop"]["loop_id"] == first["active_loop"]["loop_id"]
    assert second_fresh["active_loop"]["loop_id"] == first["active_loop"]["loop_id"]
    assert first["state"] == "sandboxed"
    objective = first["active_loop"]["objective"]
    assert objective["path"] == "Qwen warm-runtime reliability acceptance contract"
    assert objective["target"] == 65_536
    assert objective["acceptance"]["context_window"] == 65_536
    assert first["active_loop"]["candidate_lineage"]["artifact_path"] == "backend/main.py"
    assert first["journal"]["verified"] is True
    assert first["journal"]["event_count"] == 3
    assert first["promotion_authorized"] is False

    with sqlite3.connect(first_governor.journal_path) as connection:
        rows = connection.execute(
            "SELECT event_index, previous_hash, event_hash FROM improvement_events ORDER BY event_id"
        ).fetchall()
    assert [row[0] for row in rows] == [0, 1, 2]
    assert rows[0][1] == "0" * 64
    assert rows[1][1] == rows[0][2]
    assert rows[2][1] == rows[1][2]



def test_passing_self_submitted_screening_cannot_promote(tmp_path: Path) -> None:
    from backend.improvement_governor import EvidenceUnavailableError

    governor = _governor(
        tmp_path / "governor.sqlite3",
        evaluation={
            "overall_status": "passed",
            "complete": True,
            "submitted_receipt_checks_passed": True,
            "promotion_authorized": True,
        },
    )
    started = governor.start_loop()
    loop_id = started["active_loop"]["loop_id"]

    with pytest.raises(EvidenceUnavailableError):
        governor.screen(loop_id, {"candidate": {"digest": "b" * 64}})

    status = governor.status()
    assert status["state"] == "sandboxed"
    assert status["active_loop"]["screening"] is None
    assert status["human_authorization_required"] is True
    assert status["autonomous_promotion_permitted"] is False
    assert status["promotion_authorized"] is False
    assert status["stable_checkpoint"] == started["stable_checkpoint"]
    assert status["journal"]["event_count"] == 3


def test_tampered_journal_fails_closed_on_read(tmp_path: Path) -> None:
    governor = _governor(tmp_path / "governor.sqlite3")
    governor.start_loop()

    with sqlite3.connect(governor.journal_path) as connection:
        connection.execute("DROP TRIGGER improvement_events_no_update")
        connection.execute(
            "UPDATE improvement_events SET payload_json = '{}' WHERE event_index = 0"
        )

    with pytest.raises(JournalIntegrityError):
        governor.status()
    with pytest.raises(JournalIntegrityError):
        governor.start_loop()


def test_rollback_retains_stable_checkpoint_without_runtime_mutation(tmp_path: Path) -> None:
    governor = _governor(tmp_path / "governor.sqlite3")
    started = governor.start_loop()
    loop_id = started["active_loop"]["loop_id"]
    stable_checkpoint = started["stable_checkpoint"]

    rolled_back = governor.rollback(loop_id, "operator stopped the bounded trial")

    assert rolled_back["state"] == "rolled_back"
    assert rolled_back["active_loop"] is None
    assert rolled_back["latest_loop"]["stage"] == "rolled_back"
    assert rolled_back["stable_checkpoint"] == stable_checkpoint
    assert rolled_back["stable_checkpoint"]["retained"] is True
    assert rolled_back["promotion_authorized"] is False

    with sqlite3.connect(governor.journal_path) as connection:
        payload_json = connection.execute(
            "SELECT payload_json FROM improvement_events ORDER BY event_id DESC LIMIT 1"
        ).fetchone()[0]
    rollback_payload = json.loads(payload_json)
    assert rollback_payload["runtime_mutation_performed"] is False
    assert rollback_payload["stable_checkpoint_retained"] is True


def test_api_surface_exposes_no_authorize_or_promote_operation() -> None:
    from backend.improvement_governor_api import router

    operations = {
        (route.path, method)
        for route in router.routes
        for method in (route.methods or set())
    }
    assert operations == {
        ("/api/improvement/governor", "GET"),
        ("/api/improvement/governor/loops", "POST"),
        ("/api/improvement/governor/loops/{loop_id}/screen", "POST"),
        ("/api/improvement/governor/loops/{loop_id}/rollback", "POST"),
    }
    assert all("authorize" not in path and "promote" not in path for path, _ in operations)


def test_replay_rejects_self_asserted_canary_authorization(tmp_path: Path) -> None:
    governor = _governor(
        tmp_path / "governor.sqlite3",
        evaluation={"overall_status": "passed", "complete": True},
    )
    started = governor.start_loop()
    loop_id = started["active_loop"]["loop_id"]
    governor.screen(loop_id, _bound_receipt(started))

    with sqlite3.connect(governor.journal_path) as connection:
        event_index, previous_hash = connection.execute(
            """
            SELECT event_index + 1, event_hash
            FROM improvement_events
            WHERE loop_id = ?
            ORDER BY event_index DESC
            LIMIT 1
            """,
            (loop_id,),
        ).fetchone()
        _append_event(
            connection,
            loop_id=loop_id,
            event_index=event_index,
            event_type="canary",
            payload={
                "human_authorization": {
                    "kind": "human",
                    "authorization_id": "self-asserted",
                    "authorized_by": "untrusted-writer",
                    "mac": "0" * 64,
                }
            },
            previous_hash=previous_hash,
        )

    with pytest.raises(JournalIntegrityError, match="operator authorization key"):
        governor.status()


def test_replays_legacy_inconclusive_evaluation_as_unverifiable(
    tmp_path: Path,
) -> None:
    journal_path = tmp_path / "governor.sqlite3"
    legacy_receipt_digest = "a" * 64
    governor = _governor(journal_path)
    started = governor.start_loop()
    loop_id = started["active_loop"]["loop_id"]

    with governor._existing_connection() as connection:
        replay = governor._validate_and_replay(connection)
        loop = replay["loops"][loop_id]
        legacy_payload = {
            "evaluation": {
                "schema_version": 1,
                "overall_status": "incomplete",
                "decision": "incomplete",
                "promotion_authorized": False,
                "receipt_digest": legacy_receipt_digest,
            },
            "evaluation_status": "incomplete",
            "promotion_authorized": False,
            "receipt_digest": legacy_receipt_digest,
            "screening_outcome": "inconclusive",
        }
        _, evaluated_hash = governor._insert_event(
            connection,
            loop_id=loop_id,
            event_type="evaluated",
            payload=legacy_payload,
            previous_stage=loop["stage"],
            previous_hash=loop["head_hash"],
            event_index=len(loop["events"]),
        )
        governor._insert_event(
            connection,
            loop_id=loop_id,
            event_type="inconclusive",
            payload={
                "promotion_authorized": False,
                "reason": "screening_evidence_incomplete",
                "receipt_digest": legacy_receipt_digest,
            },
            previous_stage="evaluated",
            previous_hash=evaluated_hash,
            event_index=len(loop["events"]) + 1,
        )

    status = governor.status()
    screening = status["latest_loop"]["screening"]
    assert status["journal"]["integrity"] == "verified"
    assert status["state"] == "inconclusive"
    assert status["promotion_authorized"] is False
    assert screening["promotion_authorized"] is False
    assert screening["receipt_replay_verified"] is False
    assert screening["evidence"]["evidence_verification"] == {
        "schema_version": 1,
        "status": "legacy-unverifiable",
        "reason": "receipt_and_attestation_were_not_persisted",
        "promotion_ready": False,
    }


def test_replays_pre_paired_rejected_receipt_without_downgrading_hardened_lineage(
    tmp_path: Path,
) -> None:
    from backend.improvement_governor import document_digest

    def historical_governor(path: Path, *, paired_marker: bool) -> ImprovementGovernor:
        governor = _governor(path)
        loop_id = "loop-pre-paired-rejected"
        objective = "historical warm-runtime screening"
        baseline_digest = "a" * 64
        candidate_digest = "b" * 64
        lineage = {
            "parent_checkpoint_digest": "c" * 64,
            "candidate_digest": candidate_digest,
            "candidate_kind": "ollama-warm-residency-v1",
            "artifact_path": "backend/main.py",
        }
        if paired_marker:
            lineage["baseline_artifact_digest"] = "d" * 64
        binding = {
            "proposal_id": loop_id,
            "baseline_digest": baseline_digest,
            "candidate_digest": candidate_digest,
        }
        evidence = {
            "invocation_id": "legacy-invocation",
            "candidate_kind": "ollama-warm-residency-v1",
            "objective": objective,
            "artifact_path": "backend/main.py",
            "candidate_digest": candidate_digest,
            "source_digest": candidate_digest,
            "diff_digest": "d" * 64,
            "diff_bytes": 1,
            "sandbox_kind": "docker-network-none-read-only",
            "image_digest": "e" * 64,
            "executed_image_ref": f"sha256:{'e' * 64}",
            "probe_runs": 3,
            "probe_passes": 0,
            "model": "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M",
            "requested_context": 262144,
            "observed_context": 262144,
            "residency_verified": False,
            "test_digest": "f" * 64,
            "evaluator_digest": "1" * 64,
            "command_digest": "2" * 64,
            "output_digest": "3" * 64,
            "comparison": {"status": "inconclusive-baseline-not-replayable"},
            "comparison_digest": "4" * 64,
            "residency_observation_digest": "5" * 64,
        }
        statement = {
            "subject": [{
                "name": "backend/main.py",
                "digest": {"sha256": candidate_digest},
            }],
            "predicate": {"binding": binding, "evidence": evidence},
        }
        attestation = {
            "statement": statement,
            "statement_digest": document_digest(statement),
        }
        attestation["attestation_digest"] = document_digest(attestation)
        receipt = {
            "schema_version": 2,
            "receipt_kind": "obus-infrastructure-reliability-screening-v1",
            "candidate": {
                **binding,
                "candidate_kind": "ollama-warm-residency-v1",
                "objective": objective,
                "artifact_path": "backend/main.py",
                "source_digest": candidate_digest,
                "diff_digest": "d" * 64,
                "self_promotion_requested": False,
            },
            "governance": {
                "autonomous_promotion_permitted": False,
                "human_authorization": {"status": "pending"},
            },
            "_obus_candidate": {
                "binding": binding,
                "candidate_kind": "ollama-warm-residency-v1",
                "evidence_summary": evidence,
                "attestation": attestation,
            },
        }
        safe_fields = (
            "invocation_id", "candidate_kind", "objective", "artifact_path",
            "candidate_digest", "source_digest", "diff_digest", "diff_bytes",
            "sandbox_kind", "image_digest", "executed_image_ref", "probe_runs",
            "probe_passes", "model", "requested_context", "observed_context",
            "residency_verified", "test_digest", "evaluator_digest",
            "command_digest", "output_digest", "comparison", "comparison_digest",
            "residency_observation_digest",
        )
        evidence_summary = {field: evidence[field] for field in safe_fields}
        receipt_digest = document_digest(receipt)
        evaluation = {
            "overall_status": "fail",
            "decision": "rejected",
            "promotion_authorized": False,
        }
        stable_checkpoint = {
            "checkpoint_digest": "6" * 64,
            "source": "historical-test",
            "baseline_digest": baseline_digest,
            "retained": True,
        }
        with governor._existing_connection() as connection:
            head = _append_event(
                connection,
                loop_id=loop_id,
                event_index=0,
                event_type="observed",
                payload={
                    "baseline": _baseline(),
                    "baseline_digest": baseline_digest,
                    "objective": objective,
                    "stable_checkpoint": stable_checkpoint,
                },
                previous_hash="0" * 64,
            )
            head = _append_event(
                connection,
                loop_id=loop_id,
                event_index=1,
                event_type="proposed",
                payload={
                    "candidate_lineage": lineage,
                    "objective": objective,
                    "runtime_mutation_performed": False,
                },
                previous_hash=head,
            )
            head = _append_event(
                connection,
                loop_id=loop_id,
                event_index=2,
                event_type="sandboxed",
                payload={
                    "candidate_lineage": lineage,
                    "sandbox_kind": "fixed_docker_candidate_pending_evidence",
                    "runtime_mutation_performed": False,
                    "stable_checkpoint": stable_checkpoint,
                },
                previous_hash=head,
            )
            head = _append_event(
                connection,
                loop_id=loop_id,
                event_index=3,
                event_type="evaluated",
                payload={
                    "evaluation": evaluation,
                    "evaluation_status": "fail",
                    "promotion_authorized": False,
                    "receipt_digest": receipt_digest,
                    "attestation_digest": attestation["attestation_digest"],
                    "evidence_summary": evidence_summary,
                    "verification_record": receipt,
                    "screening_outcome": "rejected",
                },
                previous_hash=head,
            )
            _append_event(
                connection,
                loop_id=loop_id,
                event_index=4,
                event_type="rejected",
                payload={
                    "promotion_authorized": False,
                    "reason": "screening_failed",
                    "receipt_digest": receipt_digest,
                },
                previous_hash=head,
            )
        return governor

    legacy = historical_governor(
        tmp_path / "legacy-governor.sqlite3", paired_marker=False
    )
    status = legacy.status()
    screening = status["latest_loop"]["screening"]
    assert status["journal"]["integrity"] == "verified"
    assert status["state"] == "rejected"
    assert status["promotion_authorized"] is False
    assert screening["receipt_replay_verified"] is False
    assert screening["evidence"]["evidence_verification"] == {
        "schema_version": 1,
        "status": "legacy-unverifiable",
        "reason": "immutable_git_baseline_was_not_recorded",
        "evidence_contract_version": 1,
        "promotion_ready": False,
    }

    partially_hardened = historical_governor(
        tmp_path / "partial-governor.sqlite3", paired_marker=True
    )
    with pytest.raises(JournalIntegrityError, match="re-verification failed"):
        partially_hardened.status()


def test_replay_rejects_promoted_event_with_invalid_human_mac(tmp_path: Path) -> None:
    key = b"operator-held-governor-key-32-bytes"
    governor = _governor(
        tmp_path / "governor.sqlite3",
        evaluation={"overall_status": "passed", "complete": True},
        authorization_key=key,
    )
    started = governor.start_loop()
    loop_id = started["active_loop"]["loop_id"]
    governor.screen(loop_id, _bound_receipt(started))

    with sqlite3.connect(governor.journal_path) as connection:
        event_index, previous_hash = connection.execute(
            """
            SELECT event_index + 1, event_hash
            FROM improvement_events
            WHERE loop_id = ?
            ORDER BY event_index DESC
            LIMIT 1
            """,
            (loop_id,),
        ).fetchone()
        canary_payload = _authorized_payload(
            key,
            loop_id=loop_id,
            event_index=event_index,
            event_type="canary",
            previous_hash=previous_hash,
            authorization_id="canary-approval",
        )
        _append_event(
            connection,
            loop_id=loop_id,
            event_index=event_index,
            event_type="canary",
            payload=canary_payload,
            previous_hash=previous_hash,
        )

    with pytest.raises(JournalIntegrityError, match="final-policy evidence"):
        governor.status()


def test_schema_validation_rejects_replaced_append_only_trigger(tmp_path: Path) -> None:
    governor = _governor(tmp_path / "governor.sqlite3")
    governor.start_loop()

    with sqlite3.connect(governor.journal_path) as connection:
        connection.execute("DROP TRIGGER improvement_events_no_update")
        connection.execute(
            """
            CREATE TRIGGER improvement_events_no_update
            BEFORE UPDATE ON improvement_events
            BEGIN
                SELECT 1;
            END
            """
        )

    with pytest.raises(JournalIntegrityError, match="schema fingerprint mismatch"):
        governor.status()


def test_concurrent_first_initialization_is_race_safe(tmp_path: Path) -> None:
    journal_path = tmp_path / "governor.sqlite3"
    ready = Barrier(2)

    class RacingGovernor(ImprovementGovernor):
        def _new_connection(self) -> sqlite3.Connection:
            ready.wait(timeout=5.0)
            return super()._new_connection()

    def construct() -> dict[str, Any]:
        governor = RacingGovernor(
            journal_path,
            status_provider=_baseline,
            receipt_evaluator=lambda _receipt: {
                "overall_status": "incomplete",
                "complete": False,
            },
        )
        return governor.status()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(construct) for _ in range(2)]
        statuses = [future.result(timeout=10.0) for future in futures]

    assert [status["state"] for status in statuses] == ["idle", "idle"]
    assert all(status["journal"]["verified"] is True for status in statuses)
