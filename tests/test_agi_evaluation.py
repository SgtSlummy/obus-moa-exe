from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.agi_evaluation import (
    AGIEvaluationError,
    document_digest,
    evaluate_receipt,
    load_manifest,
    validate_manifest,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
HEX_DIGEST = "a" * 64


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    current = target
    components = path.split(".")
    for component in components[:-1]:
        current = current.setdefault(component, {})
    current[components[-1]] = value


def _passing_metrics(manifest: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for gate in manifest["gates"]:
        for check in gate["checks"]:
            _set_path(metrics, check["path"], check["value"])
    return metrics


def _run(
    manifest: dict[str, Any],
    run_id: str,
    *,
    sequence: int | None = None,
    organization: str | None = None,
    independent: bool | None = None,
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "run_id": run_id,
        "status": "completed",
        "completed_at": "2026-09-01T10:00:00Z",
        "subject": {
            "source_commit": "commit-123",
            "source_tree_digest": HEX_DIGEST,
            "provider": "ollama",
            "model": "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M",
            "model_digest": HEX_DIGEST,
            "context_window": 262144,
            "config_digest": HEX_DIGEST,
            "toolchain_digest": HEX_DIGEST,
            "provider_fallback_used": False,
            "memory_isolated": True,
        },
        "suite": {
            "dataset_digest": HEX_DIGEST,
            "evaluator_digest": HEX_DIGEST,
            "scaffold_digest": HEX_DIGEST,
            "sealed": True,
            "sealed_task_fraction": 0.25,
            "contamination_screen_passed": True,
        },
        "verifier": {
            "identity": "independent-verifier-v1",
            "method_digest": HEX_DIGEST,
            "result_digest": HEX_DIGEST,
            "independent_of_subject": True,
        },
        "critical_incidents": [],
        "artifacts": [
            {"kind": kind, "uri": f"artifact://{run_id}/{kind}", "sha256": HEX_DIGEST}
            for kind in manifest["evidence_policy"]["required_artifact_kinds"]
        ],
        "metrics": _passing_metrics(manifest),
    }
    if sequence is not None:
        run["sequence"] = sequence
    if organization is not None:
        run["operator_organization"] = organization
    if independent is not None:
        run["independent"] = independent
    return run


def _passing_receipt(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest["claim"].get("receipt_schema_version", 1),
        "claim_id": manifest["claim"]["id"],
        "claim_version": manifest["claim"]["version"],
        "manifest_digest": document_digest(manifest),
        "operator_organization": "Obus Project",
        "campaign": {"id": "campaign-001", "complete_run_ledger": True},
        "primary_runs": [
            _run(manifest, f"primary-{sequence}", sequence=sequence)
            for sequence in range(1, 4)
        ],
        "independent_replications": [
            _run(
                manifest,
                "replication-1",
                organization="Independent Lab",
                independent=True,
            )
        ],
    }


def _gate(result: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(gate for gate in result["gates"] if gate["id"] == gate_id)


def test_manifest_separates_source_metrics_from_obus_policy_thresholds() -> None:
    manifest = load_manifest()

    assert manifest["schema_version"] == 2
    assert manifest["claim"]["version"] == "2.0.0"
    assert manifest["claim"]["target_level"] == "A23"
    assert manifest["claim"]["current_level"] == "A2"
    assert manifest["claim"]["gate_count"] == 23
    assert manifest["claim"]["receipt_schema_version"] == 2
    assert len(manifest["gates"]) == 23
    assert len({gate["id"] for gate in manifest["gates"]}) == 23
    assert manifest["evidence_policy"]["minimum_passed_gate_count"] == 23
    assert manifest["evidence_policy"]["self_certification_permitted"] is False
    assert manifest["evidence_policy"]["api_submissions_can_authorize"] is False
    assert manifest["evidence_policy"]["external_artifact_rehash_required"] is True
    assert (
        manifest["evidence_policy"]["authenticated_independent_attestation_required"]
        is True
    )
    assert "without hidden human task intervention" in manifest["claim"]["definition"]
    assert all(gate["source_defined_metric"] for gate in manifest["gates"])
    assert all(gate["obus_normative_threshold"] for gate in manifest["gates"])
    assert all(
        check["threshold_origin"] in {"source-defined", "obus-policy"}
        for gate in manifest["gates"]
        for check in gate["checks"]
    )
    assert any(
        check["threshold_origin"] == "obus-policy"
        for gate in manifest["gates"]
        for check in gate["checks"]
    )


def test_invalid_manifest_is_rejected_before_receipt_evaluation() -> None:
    manifest = load_manifest()
    manifest["gates"][0]["checks"][0]["operator"] = "execute-arbitrary-code"

    with pytest.raises(AGIEvaluationError):
        validate_manifest(manifest)


def test_missing_evidence_is_incomplete_and_never_claimable() -> None:
    manifest = load_manifest()

    result = evaluate_receipt({}, manifest, now=NOW)

    assert result["overall_status"] == "incomplete"
    assert result["qualification"] == "not_earned"
    assert result["claim_permitted"] is False
    assert result["reported_level"] == "A2"
    assert result["blockers"]


def test_self_authored_passing_receipt_is_candidate_only_and_cannot_authorize_a23() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "passed"
    assert result["qualification"] == "candidate_passed"
    assert result["claim_permitted"] is False
    assert result["reported_level"] == "A2"
    assert result["required_gate_count"] == 23
    assert result["passed_gate_count"] == 23
    assert result["submitted_receipt_checks_passed"] is True
    assert result["receipt_provenance_declared"] is True
    assert result["receipt_provenance_present"] is False
    assert result["external_verification_status"] == "required"
    assert result["api_submission_can_authorize"] is False
    assert result["claim_statement"] == manifest["claim"]["unearned_statement"]
    assert result["blockers"] == ["external_verification.required"]


def test_one_below_threshold_metric_fails_everything_without_averaging() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["primary_runs"][1]["metrics"]["benchmarks"]["gaia"]["overall_accuracy"] = 0.919

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert result["claim_permitted"] is False
    assert _gate(result, "general_assistance")["status"] == "failed"


def test_missing_metric_is_incomplete_not_a_silent_pass() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    del receipt["primary_runs"][0]["metrics"]["learning"]["heldout_leakage_detected"]

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "incomplete"
    assert _gate(result, "continual_learning")["status"] == "incomplete"
    assert result["claim_permitted"] is False


def test_provider_fallback_contaminates_the_receipt() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["primary_runs"][2]["subject"]["provider_fallback_used"] = True

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert "primary-3.no_fallback" in result["blockers"]


def test_subject_identity_must_remain_frozen_across_replication() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["independent_replications"][0]["subject"]["model_digest"] = "b" * 64

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert "frozen_identity.subject.model_digest" in result["blockers"]


def test_replication_by_same_organization_is_not_independent() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["independent_replications"][0]["operator_organization"] = "  ＯＢＵＳ PROJECT  "

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert "replication-1.organization" in result["blockers"]


def test_metr_current_reliability_ceiling_cannot_be_called_a_40_hour_pass() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["primary_runs"][0]["metrics"]["benchmarks"]["metr"][
        "validated_measurement_ceiling_hours"
    ] = 16

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert _gate(result, "validated_task_horizon")["status"] == "failed"


def test_stale_evidence_and_boolean_numeric_spoofing_fail_closed() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["primary_runs"][0]["completed_at"] = "2025-01-01T00:00:00Z"
    receipt["primary_runs"][1]["metrics"]["benchmarks"]["arc_agi_2"]["private_accuracy"] = True

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert "primary-1.recency" in result["blockers"]
    assert _gate(result, "novel_skill_acquisition")["status"] == "incomplete"


def test_a23_manifest_fails_closed_on_gate_count_or_self_certification_drift() -> None:
    manifest = load_manifest()
    manifest["gates"].pop()

    with pytest.raises(AGIEvaluationError, match="exactly 23 gates"):
        validate_manifest(manifest)

    manifest = load_manifest()
    manifest["evidence_policy"]["self_certification_permitted"] = True

    with pytest.raises(AGIEvaluationError, match="must be false"):
        validate_manifest(manifest)

    manifest = load_manifest()
    manifest["claim"]["current_level"] = "A23"

    with pytest.raises(AGIEvaluationError, match="pre-A23 verified level"):
        validate_manifest(manifest)


def test_twenty_two_of_twenty_three_gates_cannot_earn_a23() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["primary_runs"][0]["metrics"]["evaluation"]["self_authorized_promotions"] = 1

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["overall_status"] == "failed"
    assert result["qualification"] == "not_earned"
    assert result["claim_permitted"] is False
    assert result["reported_level"] == "A2"
    assert result["passed_gate_count"] == 22
    assert _gate(result, "evaluator_noninterference")["status"] == "failed"


def test_primary_operator_cannot_self_certify_without_independent_replication() -> None:
    manifest = load_manifest()
    receipt = _passing_receipt(manifest)
    receipt["independent_replications"] = []

    result = evaluate_receipt(receipt, manifest, now=NOW)

    assert result["claim_permitted"] is False
    assert result["receipt_provenance_present"] is False
    assert "replications.count" in result["blockers"]


def test_legacy_v1_contract_remains_readable_but_cannot_report_a23() -> None:
    manifest = deepcopy(load_manifest())
    manifest["schema_version"] = 1
    manifest["claim"]["version"] = "1.0.0"
    manifest["claim"]["target_level"] = "A4"
    manifest["claim"].pop("gate_count")
    manifest["claim"].pop("receipt_schema_version")
    manifest["claim"]["qualified_statement"] = "Legacy A4 qualification."
    manifest["claim"]["unearned_statement"] = "Legacy A4 not earned."
    manifest["evidence_policy"].pop("minimum_independent_organizations")
    manifest["evidence_policy"].pop("minimum_passed_gate_count")
    manifest["evidence_policy"].pop("self_certification_permitted")
    manifest["evidence_policy"].pop("api_submissions_can_authorize")
    manifest["evidence_policy"].pop("external_artifact_rehash_required")
    manifest["evidence_policy"].pop("authenticated_independent_attestation_required")
    manifest["gates"] = manifest["gates"][:11]
    validate_manifest(manifest)

    result = evaluate_receipt(_passing_receipt(manifest), manifest, now=NOW)

    assert result["qualification"] == "candidate_passed"
    assert result["claim_permitted"] is False
    assert result["reported_level"] == "A2"
    assert result["reported_level"] != "A23"
    assert result["required_gate_count"] == 11
