from __future__ import annotations

import copy
from pathlib import Path

import pytest

from backend import improvement_candidate as candidate
from backend.improvement_evaluation import evaluate_improvement_screening_receipt
from backend.improvement_governor import (
    EvidenceUnavailableError,
    ImprovementGovernor,
    _screening_stage,
)


BASELINE_DIGEST = "a" * 64
CANDIDATE_DIGEST = candidate.REVIEW_CANDIDATE_ARTIFACT_DIGEST
OBJECTIVE = (
    "Improve Qwen warm-runtime reliability by verifying the configured "
    "65536-token context and indefinite residency with a fixed public contract."
)


def _loop_view(source_digest: str | None = None) -> dict:
    source_digest = source_digest or candidate._file_digest(
        Path(candidate.__file__).with_name("main.py")
    )
    baseline_artifact = candidate.load_warm_runtime_baseline_artifact()
    return {
        "loop_id": "loop-evidence-001",
        "objective": OBJECTIVE,
        "baseline_digest": BASELINE_DIGEST,
        "candidate_lineage": {
            "baseline_source_revision": baseline_artifact["source_revision"],
            "baseline_artifact_digest": baseline_artifact["artifact_digest"],
            "baseline_artifact": baseline_artifact,
            "candidate_digest": source_digest,
            "candidate_kind": candidate.CANDIDATE_KIND,
            "artifact_path": "backend/main.py",
        },
    }


def _candidate_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source_digest: str | None = None,
) -> dict:
    monkeypatch.setenv(candidate.ATTESTATION_KEY_ENV, "k" * 32)
    monkeypatch.setattr(candidate, "_docker_image_digest", lambda: "c" * 64)
    source_digest = source_digest or candidate._file_digest(
        Path(candidate.__file__).with_name("main.py")
    )

    def file_digest(path: Path) -> str:
        if path.name == "main.py":
            return source_digest
        if path.name == "test_runtime.py":
            return "d" * 64
        return "e" * 64

    monkeypatch.setattr(candidate, "_file_digest", file_digest)
    monkeypatch.setattr(
        candidate,
        "_git_diff_evidence",
        lambda _root: {
            "base": "HEAD",
            "artifact_path": "backend/main.py",
            "diff_digest": "f" * 64,
            "diff_bytes": 123,
        },
    )

    def run_fixed_probes(
        root: Path,
        *,
        phase: str = "candidate",
        artifact_override: Path | None = None,
    ) -> tuple[list[dict], str]:
        command = candidate._canonical_probe_command(
            candidate._probe_argv(root, artifact_override=artifact_override)
        )
        command_digest = candidate._digest(command)
        passed = phase == "candidate"
        return (
            [
                {
                    "phase": phase,
                    "run": index,
                    "exit_code": 0 if passed else 1,
                    "duration_ms": 10,
                    "image_digest": "c" * 64,
                    "command": list(command),
                    "command_digest": command_digest,
                    "output_digest": (str(index) if passed else "b") * 64,
                    "passed": passed,
                    "failure_kind": None,
                }
                for index in range(1, 4)
            ],
            command_digest,
        )

    monkeypatch.setattr(candidate, "_run_fixed_probes", run_fixed_probes)
    residency = {
        "model": candidate.MODEL,
        "requested_context": candidate.REQUESTED_CONTEXT,
        "keep_alive": -1,
        "generation_done": True,
        "resident": True,
        "observed_context": candidate.REQUESTED_CONTEXT,
        "verified": True,
        "failure": None,
    }
    residency["observation_digest"] = candidate._digest(residency)
    monkeypatch.setattr(candidate, "_verify_ollama_residency", lambda: residency)
    return candidate.run_improvement_candidate(
        candidate.CANDIDATE_KIND,
        loop=_loop_view(source_digest),
    )


def test_fixed_candidate_builds_measured_pending_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _candidate_result(monkeypatch)
    receipt = result["receipt"]

    assert receipt["candidate"]["objective"] == OBJECTIVE
    assert receipt["candidate"]["candidate_digest"] == candidate._file_digest(
        Path(candidate.__file__).with_name("main.py")
    )
    assert receipt["measurement"]["reproducibility"]["heldout"] is False
    assert receipt["measurement"]["comparison"]["baseline_replayable"] is True
    assert receipt["measurement"]["comparison"]["improved"] is True
    assert receipt["candidate"]["baseline_artifact_digest"]
    baseline_revision = receipt["candidate"]["baseline_source_revision"]
    assert len(baseline_revision) in {40, 64}
    assert baseline_revision != "HEAD"
    assert set(receipt["_obus_candidate"]["baseline_artifact"]) == {
        "artifact_path", "source_revision", "artifact_digest",
    }
    assert "baseline_artifact" not in receipt["_obus_candidate"]["evidence_summary"]
    assert receipt["_obus_candidate"]["evidence_summary"]["baseline_manifest_digest"]
    assert receipt["_obus_candidate"]["evidence_summary"]["candidate_manifest_digest"]
    assert receipt["rollback"]["restore_status"] == "not-measured"
    assert receipt["governance"]["human_authorization"] == {"status": "pending"}
    assert all(
        run["command_digest"] == candidate._digest(run["command"])
        for run in receipt["measurement"]["reproducibility"]["runs"]
    )
    evaluation = evaluate_improvement_screening_receipt(receipt)
    assert evaluation["overall_status"] == "pass", evaluation
    assert evaluation["decision"] == "ready-for-human-authorization"
    assert evaluation["promotion_authorized"] is False
    assert _screening_stage(evaluation) == "awaiting_authorization"

    embedded_source = copy.deepcopy(receipt)
    embedded_source["_obus_candidate"]["baseline_artifact"]["content"] = "dGFtcGVyZWQ="
    rejected_source = evaluate_improvement_screening_receipt(embedded_source)
    assert rejected_source["overall_status"] == "fail"
    assert any("baseline artifact metadata" in check for check in rejected_source["failed_checks"])

    rebound = copy.deepcopy(receipt)
    fake_revision = "0" * 40
    rebound["candidate"]["baseline_source_revision"] = fake_revision
    rebound["_obus_candidate"]["binding"]["baseline_source_revision"] = fake_revision
    rebound["_obus_candidate"]["baseline_artifact"]["source_revision"] = fake_revision
    rebound["_obus_candidate"]["evidence_summary"]["baseline_source_revision"] = fake_revision
    rebound["_obus_candidate"]["evidence_summary"]["baseline_manifest"][
        "source_revision"
    ] = fake_revision
    rebound_extension = rebound["_obus_candidate"]
    rebound_evidence = rebound_extension["evidence_summary"]
    rebound_evidence["baseline_manifest_digest"] = candidate._digest(
        rebound_evidence["baseline_manifest"]
    )
    rebound_statement = rebound_extension["attestation"]["statement"]
    rebound_statement["subject"][1]["name"] = (
        f"baseline:{fake_revision}:backend/main.py"
    )
    rebound_statement["predicate"]["binding"] = copy.deepcopy(
        rebound_extension["binding"]
    )
    rebound_statement["predicate"]["evidence"] = copy.deepcopy(rebound_evidence)
    for dependency in rebound_statement["predicate"]["buildDefinition"][
        "resolvedDependencies"
    ]:
        if str(dependency["uri"]).startswith("baseline:"):
            dependency["uri"] = f"baseline:{fake_revision}:backend/main.py"
        elif dependency["uri"] == "manifest:baseline-arm":
            dependency["digest"]["sha256"] = rebound_evidence[
                "baseline_manifest_digest"
            ]
    rebound_extension["attestation"] = candidate._sign_attestation(
        rebound_statement, b"k" * 32
    )
    rejected_rebind = evaluate_improvement_screening_receipt(rebound)
    assert rejected_rebind["overall_status"] == "fail"
    assert any(
        "immutable Git baseline" in check for check in rejected_rebind["failed_checks"]
    )

    identical = copy.deepcopy(receipt)
    identical["candidate"]["baseline_artifact_digest"] = identical["candidate"][
        "candidate_digest"
    ]
    rejected_identical = evaluate_improvement_screening_receipt(identical)
    assert rejected_identical["overall_status"] == "fail"
    assert "baseline and candidate artifacts must be distinct" in rejected_identical[
        "failed_checks"
    ]

    claimed_not_improved = copy.deepcopy(receipt)
    comparison = claimed_not_improved["measurement"]["comparison"]
    comparison["improved"] = False
    comparison["qualification"] = "no-measured-improvement"
    comparison["comparison_digest"] = candidate._digest(
        {key: value for key, value in comparison.items() if key != "comparison_digest"}
    )
    claimed_not_improved["_obus_candidate"]["evidence_summary"]["comparison"] = copy.deepcopy(
        comparison
    )
    claimed_not_improved["_obus_candidate"]["evidence_summary"][
        "comparison_digest"
    ] = comparison["comparison_digest"]
    claim_extension = claimed_not_improved["_obus_candidate"]
    claim_statement = claim_extension["attestation"]["statement"]
    claim_statement["predicate"]["evidence"] = copy.deepcopy(
        claim_extension["evidence_summary"]
    )
    claim_extension["attestation"] = candidate._sign_attestation(
        claim_statement, b"k" * 32
    )
    rejected_claim = evaluate_improvement_screening_receipt(claimed_not_improved)
    assert rejected_claim["overall_status"] == "fail"
    assert "paired improvement claim does not match derived scores" in rejected_claim[
        "failed_checks"
    ]

    command_tampered = copy.deepcopy(receipt)
    command_tampered["measurement"]["reproducibility"]["runs"][0]["command_digest"] = "0" * 64
    rejected_command = evaluate_improvement_screening_receipt(command_tampered)
    assert rejected_command["overall_status"] == "fail"

    dsse_tampered = copy.deepcopy(receipt)
    dsse_tampered["_obus_candidate"]["attestation"]["envelope"]["signatures"][0]["sig"] = "AA=="
    rejected_dsse = evaluate_improvement_screening_receipt(dsse_tampered)
    assert rejected_dsse["overall_status"] == "fail"
    assert any("DSSE" in check for check in rejected_dsse["failed_checks"])

    payload_tampered = copy.deepcopy(receipt)
    payload_tampered["_obus_candidate"]["attestation"]["envelope"]["payload"] = (
        "eyJ0YW1wZXJlZCI6dHJ1ZX0="
    )
    rejected_payload = evaluate_improvement_screening_receipt(payload_tampered)
    assert rejected_payload["overall_status"] == "fail"
    assert any(
        "DSSE payload" in check and "stored statement" in check
        for check in rejected_payload["failed_checks"]
    )

    self_approved = copy.deepcopy(receipt)
    self_approved["governance"]["human_authorization"] = {
        "status": "approved",
        "approver_kind": "candidate",
    }
    rejected = evaluate_improvement_screening_receipt(self_approved)
    assert rejected["overall_status"] == "fail"
    assert rejected["promotion_authorized"] is False


def test_runner_is_allowlisted_immutable_and_loop_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(candidate.UnsupportedCandidateError):
        candidate.run_improvement_candidate("arbitrary-shell", loop=_loop_view())

    monkeypatch.setattr(candidate, "_docker_image_digest", lambda: "c" * 64)
    argv = candidate._probe_argv(Path("C:/workspace"))
    assert "obus-dev:latest" not in argv
    assert f"sha256:{'c' * 64}" in argv
    assert any(item.startswith("type=bind,source=") for item in argv)
    canonical = candidate._canonical_probe_command(argv)
    other_root = candidate._canonical_probe_command(
        candidate._probe_argv(Path("D:/different-workspace"))
    )
    assert any("<repo-mount>" in item for item in canonical)
    assert canonical == other_root
    assert candidate._digest(canonical) == candidate._digest(other_root)

    receipt = _candidate_result(monkeypatch)["receipt"]
    journal_loop = {
        "loop_id": "loop-evidence-001",
        "events": [
            {
                "stage": "observed",
                "payload": {
                    "baseline_digest": BASELINE_DIGEST,
                    "baseline_source_revision": _loop_view()["candidate_lineage"][
                        "baseline_source_revision"
                    ],
                    "baseline_artifact_digest": _loop_view()["candidate_lineage"][
                        "baseline_artifact_digest"
                    ],
                    "objective": OBJECTIVE,
                },
            },
            {"stage": "proposed", "payload": {"candidate_lineage": _loop_view()["candidate_lineage"]}},
        ],
    }
    summary, attestation_digest = ImprovementGovernor._candidate_screening_evidence(
        journal_loop, receipt
    )
    assert summary["probe_passes"] == 6
    assert summary["source_digest"] == receipt["candidate"]["candidate_digest"]
    assert attestation_digest == receipt["_obus_candidate"]["attestation"]["attestation_digest"]

    stale = copy.deepcopy(receipt)
    stale["_obus_candidate"]["binding"]["candidate_digest"] = "f" * 64
    with pytest.raises(EvidenceUnavailableError):
        ImprovementGovernor._candidate_screening_evidence(journal_loop, stale)


def test_unretained_artifact_is_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(
        candidate.CandidateRunError,
        match="candidate digest does not match current backend/main.py bytes",
    ):
        _candidate_result(monkeypatch, source_digest="7" * 64)
