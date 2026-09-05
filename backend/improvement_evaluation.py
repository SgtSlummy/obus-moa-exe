"""Deterministic, fail-closed evaluation for Obus improvement receipts.

This module evaluates evidence only. It never edits source, promotes a candidate,
or invokes rollback. Production promotion remains a separately authorized action.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "autonomous-improvement-policy.json"
)
_MISSING = object()


def _screening_canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _screening_path(document: Mapping[str, Any], path: str) -> Any:
    current: Any = document
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def _screening_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )





_SCREENING_KIND = "obus-infrastructure-reliability-screening-v1"
_SCREENING_CANDIDATE_KIND = "ollama-warm-residency-v1"
_SCREENING_SUITE_ID = "warm-runtime-focused-contract-v1"
_SCREENING_MODEL = "hf.co/OBLITERATUS/Qwen3.8-27B-OBLITERATED:Q4_K_M"
_SCREENING_CONTEXT = 65_536
_SCREENING_BASELINE_ARTIFACT = "02437041e5b9149076901a3c8e68aa0a426cc5aca16b926b36255814cb2a83f1"
_SCREENING_CANDIDATE_ARTIFACT = "9b865e739fc135d3cb901320dec0ef3ffd041976239a7dfe5c0b272953357b20"
_SCREENING_BASELINE_RECEIPTS = ("commit-293", "commit-294")
_SCREENING_CANDIDATE_RECEIPTS = (
    "commit-325", "commit-326", "commit-328", "commit-330", "commit-332"
)


def _screening_without_digest(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {name: item for name, item in value.items() if name != field}


import base64
import binascii
import hmac
import os


def _screening_dsse_pae(payload_type: str, payload: bytes) -> bytes:
    kind = payload_type.encode("utf-8")
    return (
        b"DSSEv1 "
        + str(len(kind)).encode("ascii")
        + b" "
        + kind
        + b" "
        + str(len(payload)).encode("ascii")
        + b" "
        + payload
    )


def _screening_attestation_failures(extension: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    attestation = extension.get("attestation")
    binding = extension.get("binding")
    evidence = extension.get("evidence_summary")
    if not isinstance(attestation, Mapping):
        return ["candidate attestation is malformed"]
    statement = attestation.get("statement")
    envelope = attestation.get("envelope")
    if not isinstance(statement, Mapping):
        return ["candidate attestation statement is malformed"]
    if not isinstance(envelope, Mapping):
        return ["candidate DSSE envelope is malformed"]

    payload_type = envelope.get("payloadType")
    encoded_payload = envelope.get("payload")
    if payload_type != "application/vnd.in-toto+json":
        failures.append("candidate DSSE payload type is invalid")
    payload: bytes | None = None
    decoded_statement: Any = None
    if not isinstance(encoded_payload, str):
        failures.append("candidate DSSE payload is missing")
    else:
        try:
            payload = base64.b64decode(encoded_payload, validate=True)
            decoded_statement = json.loads(payload.decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            failures.append("candidate DSSE payload is not canonical JSON")
    if payload is not None:
        canonical_payload = _screening_canonical_json(decoded_statement).encode("utf-8")
        if payload != canonical_payload or decoded_statement != dict(statement):
            failures.append("candidate DSSE payload does not canonically equal the stored statement")
        if attestation.get("statement_digest") != hashlib.sha256(payload).hexdigest():
            failures.append("candidate attestation statement digest does not match DSSE payload")

    attestation_digest = attestation.get("attestation_digest")
    if not _screening_digest(attestation_digest) or attestation_digest != _screening_digest_value(
        _screening_without_digest(attestation, "attestation_digest")
    ):
        failures.append("candidate attestation envelope digest does not match")

    key = os.environ.get("OBUS_IMPROVEMENT_ATTESTATION_KEY", "").encode("utf-8")
    signatures = envelope.get("signatures")
    if len(key) < 32:
        failures.append("trusted-host attestation key is unavailable")
    elif payload is None or not isinstance(payload_type, str):
        failures.append("candidate DSSE signature cannot be verified")
    elif not isinstance(signatures, list) or len(signatures) != 1 or not isinstance(signatures[0], Mapping):
        failures.append("candidate DSSE envelope must contain one trusted-host signature")
    else:
        signature = signatures[0]
        try:
            supplied_signature = base64.b64decode(str(signature.get("sig") or ""), validate=True)
        except (binascii.Error, ValueError):
            supplied_signature = b""
        expected_signature = hmac.new(
            key,
            _screening_dsse_pae(payload_type, payload),
            hashlib.sha256,
        ).digest()
        expected_key_id = hashlib.sha256(key).hexdigest()[:16]
        if signature.get("keyid") != expected_key_id or not hmac.compare_digest(
            supplied_signature, expected_signature
        ):
            failures.append("candidate DSSE envelope signature does not verify")

    subject = statement.get("subject")
    expected_candidate = binding.get("candidate_digest") if isinstance(binding, Mapping) else None
    expected_baseline = (
        binding.get("baseline_artifact_digest") if isinstance(binding, Mapping) else None
    )
    expected_revision = (
        binding.get("baseline_source_revision") if isinstance(binding, Mapping) else None
    )
    revision_is_full_oid = (
        isinstance(expected_revision, str)
        and len(expected_revision) in {40, 64}
        and expected_revision == expected_revision.lower()
        and all(character in "0123456789abcdef" for character in expected_revision)
    )
    subjects = (
        {
            item.get("name"): item.get("digest", {}).get("sha256")
            for item in subject
            if isinstance(item, Mapping) and isinstance(item.get("digest"), Mapping)
        }
        if isinstance(subject, list)
        else {}
    )
    if (
        not revision_is_full_oid
        or not isinstance(subject, list)
        or len(subject) != 2
        or subjects != {
            "backend/main.py": expected_candidate,
            f"baseline:{expected_revision}:backend/main.py": expected_baseline,
        }
    ):
        failures.append("candidate attestation subjects do not bind the paired artifacts")
    predicate = statement.get("predicate")
    if not isinstance(predicate, Mapping):
        failures.append("candidate attestation predicate is malformed")
    else:
        if predicate.get("binding") != binding:
            failures.append("candidate attestation binding does not match")
        if predicate.get("evidence") != evidence:
            failures.append("candidate attestation evidence does not match")
        limitations = predicate.get("limitations")
        if not isinstance(limitations, list) or not any(
            isinstance(item, str) and "does not prove" in item.lower() for item in limitations
        ):
            failures.append("candidate attestation omits its truth limitation")
    return failures


def _screening_digest_value(value: Any) -> str:
    return hashlib.sha256(_screening_canonical_json(value).encode("utf-8")).hexdigest()


def build_improvement_screening_receipt(
    *,
    binding: Mapping[str, str],
    evidence_summary: Mapping[str, Any],
    attestation: Mapping[str, Any],
    baseline_artifact: Mapping[str, Any],
    baseline_probe_runs: list[Mapping[str, Any]],
    probe_runs: list[Mapping[str, Any]],
    residency: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an evidence-only receipt; authorization remains explicitly pending."""

    policy = load_policy()
    comparison = evidence_summary.get("comparison")
    image_digest = evidence_summary.get("image_digest")
    declared_probe_runs = evidence_summary.get("probe_runs")
    declared_arm_order = evidence_summary.get("arm_execution_order")
    counterbalanced = (
        isinstance(declared_probe_runs, int)
        and not isinstance(declared_probe_runs, bool)
        and declared_probe_runs == 6
        and declared_arm_order == ["baseline", "candidate", "candidate", "baseline"]
    )
    required_runs = 6 if counterbalanced else 3
    return {
        "schema_version": 2,
        "receipt_kind": _SCREENING_KIND,
        "policy_id": policy["policy"]["id"],
        "policy_version": policy["policy"]["version"],
        "policy_digest": document_digest(policy),
        "candidate": {
            "proposal_id": str(binding["proposal_id"]),
            "evidence_contract_version": evidence_summary.get(
                "evidence_contract_version"
            ),
            "candidate_kind": str(evidence_summary.get("candidate_kind") or ""),
            "objective": str(evidence_summary.get("objective") or ""),
            "artifact_path": str(evidence_summary.get("artifact_path") or ""),
            "baseline_digest": str(binding["baseline_digest"]),
            "baseline_source_revision": str(binding["baseline_source_revision"]),
            "baseline_artifact_digest": str(binding["baseline_artifact_digest"]),
            "candidate_digest": str(binding["candidate_digest"]),
            "source_digest": str(evidence_summary.get("source_digest") or ""),
            "diff_digest": str(evidence_summary.get("diff_digest") or ""),
            "diff_bytes": evidence_summary.get("diff_bytes"),
            "self_promotion_requested": False,
        },
        "measurement": {
            "comparison": dict(comparison) if isinstance(comparison, Mapping) else comparison,
            "reproducibility": {
                "suite_id": _SCREENING_SUITE_ID,
                "suite_kind": "fixed-public-contract",
                "heldout": False,
                "required_runs": required_runs,
                "counterbalanced": counterbalanced,
                "arm_execution_order": list(declared_arm_order) if counterbalanced else None,
                "baseline_runs": [dict(run) for run in baseline_probe_runs],
                "baseline_replayed": len(baseline_probe_runs) == required_runs
                and all(
                    not isinstance(run.get("exit_code"), bool)
                    and isinstance(run.get("exit_code"), int)
                    and run.get("failure_kind") is None
                    for run in baseline_probe_runs
                ),
                "runs": [dict(run) for run in probe_runs],
                "all_passed": len(probe_runs) == required_runs
                and all(
                    run.get("passed") is True and run.get("exit_code") == 0
                    for run in probe_runs
                ),
            },
            "residency": dict(residency),
        },
        "isolation": {
            "sandboxed": True,
            "network_default_deny": True,
            "bounded_resources": True,
            "image_tag_inspected": "obus-dev:latest",
            "image_digest": image_digest,
            "executed_image_ref": evidence_summary.get("executed_image_ref"),
        },
        "governance": {
            "policy_boundary_changed": False,
            "human_authorization": {"status": "pending"},
            "autonomous_promotion_permitted": False,
        },
        "rollback": {
            "checkpoint_digest": str(binding["baseline_digest"]),
            "restore_status": "not-measured",
        },
        "_obus_candidate": {
            "binding": dict(binding),
            "candidate_kind": _SCREENING_CANDIDATE_KIND,
            "evidence_summary": dict(evidence_summary),
            "baseline_artifact": {
                "artifact_path": str(baseline_artifact.get("artifact_path") or ""),
                "source_revision": str(baseline_artifact.get("source_revision") or ""),
                "artifact_digest": str(baseline_artifact.get("artifact_digest") or ""),
            },
            "baseline_probe_runs": [dict(run) for run in baseline_probe_runs],
            "probe_runs": [dict(run) for run in probe_runs],
            "residency": dict(residency),
            "attestation": dict(attestation),
        },
    }


def _screening_observation_count(value: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in value:
            return value[name]
    return None


def _screening_phase_runs_valid(
    value: Any,
    phase: str,
    required_runs: int,
    image_digest: Any,
) -> bool:
    """Return whether a phase has complete, sealed, canonical probe evidence."""

    if not isinstance(value, list) or len(value) != required_runs:
        return False
    canonical_commands: list[list[str]] = []
    for index, run in enumerate(value, start=1):
        if not isinstance(run, Mapping):
            return False
        command = run.get("command")
        command_is_canonical = (
            isinstance(command, list)
            and all(isinstance(part, str) for part in command)
            and run.get("command_digest") == _screening_digest_value(command)
            and f"sha256:{image_digest}" in command
            and "obus-dev:latest" not in command
        )
        if isinstance(command, list):
            canonical_commands.append(command)
        exit_code = run.get("exit_code")
        if (
            run.get("phase") != phase
            or run.get("run") != index
            or isinstance(exit_code, bool)
            or not isinstance(exit_code, int)
            or run.get("passed") is not (exit_code == 0)
            or run.get("failure_kind") is not None
            or run.get("image_digest") != image_digest
            or not command_is_canonical
            or not _screening_digest(run.get("output_digest"))
        ):
            return False
    return len(canonical_commands) == required_runs and all(
        command == canonical_commands[0] for command in canonical_commands[1:]
    )


def _screening_observation_matches(
    observation: Mapping[str, Any] | None,
    phase_runs: Any,
    artifact_digest: Any,
) -> bool:
    """Return whether a retained observation is fully derived from sealed runs."""

    if not isinstance(observation, Mapping) or not isinstance(phase_runs, list):
        return False
    passed = sum(
        1
        for run in phase_runs
        if isinstance(run, Mapping) and run.get("passed") is True
    )
    total = len(phase_runs)
    return (
        observation.get("artifact_digest") == artifact_digest
        and observation.get("passed") == passed
        and observation.get("failed") == total - passed
        and observation.get("total") == total
        and observation.get("score") == (passed / total if total else 0.0)
        and observation.get("output_digest") == _screening_digest_value(phase_runs)
    )


def evaluate_improvement_screening_receipt(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate measured screening evidence without authorizing promotion."""

    policy_document = load_policy() if policy is None else dict(policy)
    validate_policy(policy_document)
    if not isinstance(receipt, Mapping):
        return {
            "overall_status": "incomplete",
            "decision": "insufficient-evidence",
            "promotion_authorized": False,
            "human_authorization_status": "pending",
            "missing_fields": ["receipt"],
            "unverifiable_fields": [],
            "failed_checks": [],
        }

    required_paths = (
        "schema_version", "receipt_kind", "policy_id", "policy_version", "policy_digest",
        "candidate.proposal_id", "candidate.evidence_contract_version",
        "candidate.candidate_kind", "candidate.objective",
        "candidate.artifact_path", "candidate.baseline_digest",
        "candidate.baseline_source_revision", "candidate.baseline_artifact_digest",
        "candidate.candidate_digest",
        "candidate.source_digest", "candidate.diff_digest", "candidate.diff_bytes",
        "candidate.self_promotion_requested", "measurement.comparison",
        "measurement.reproducibility.suite_id", "measurement.reproducibility.suite_kind",
        "measurement.reproducibility.heldout", "measurement.reproducibility.required_runs",
        "measurement.reproducibility.baseline_runs",
        "measurement.reproducibility.baseline_replayed",
        "measurement.reproducibility.runs", "measurement.reproducibility.all_passed",
        "measurement.residency", "isolation.sandboxed", "isolation.network_default_deny",
        "isolation.bounded_resources", "isolation.image_tag_inspected",
        "isolation.image_digest", "isolation.executed_image_ref",
        "governance.policy_boundary_changed", "governance.human_authorization.status",
        "governance.autonomous_promotion_permitted", "rollback.checkpoint_digest",
        "rollback.restore_status", "_obus_candidate.binding",
        "_obus_candidate.evidence_summary", "_obus_candidate.baseline_artifact",
        "_obus_candidate.baseline_probe_runs", "_obus_candidate.probe_runs",
        "_obus_candidate.residency", "_obus_candidate.attestation",
    )
    missing = [path for path in required_paths if _screening_path(receipt, path) is None]
    failures: list[str] = []
    unverifiable: list[str] = []
    candidate = receipt.get("candidate")
    measurement = receipt.get("measurement")
    isolation = receipt.get("isolation")
    governance = receipt.get("governance")
    rollback = receipt.get("rollback")
    extension = receipt.get("_obus_candidate")
    required_sections = {
        "candidate": candidate,
        "measurement": measurement,
        "isolation": isolation,
        "governance": governance,
        "rollback": rollback,
        "_obus_candidate": extension,
    }
    malformed_sections = [
        name for name, value in required_sections.items() if not isinstance(value, Mapping)
    ]
    if not missing and malformed_sections:
        missing.extend(f"{name} section" for name in malformed_sections)

    if not missing:
        receipt_reproducibility = measurement.get("reproducibility")
        counterbalanced = (
            isinstance(receipt_reproducibility, Mapping)
            and receipt_reproducibility.get("required_runs") == 6
            and receipt_reproducibility.get("counterbalanced") is True
            and receipt_reproducibility.get("arm_execution_order")
            == ["baseline", "candidate", "candidate", "baseline"]
        )
        required_probe_runs = 6 if counterbalanced else 3
        expected_measurement_source = (
            f"live-{required_probe_runs}-fixed-container-probes"
        )
        expected_policy = policy_document["policy"]
        if receipt.get("schema_version") != 2 or receipt.get("receipt_kind") != _SCREENING_KIND:
            failures.append("screening receipt schema is unsupported")
        if receipt.get("policy_id") != expected_policy["id"]:
            failures.append("policy id does not match")
        if receipt.get("policy_version") != expected_policy["version"]:
            failures.append("policy version does not match")
        if receipt.get("policy_digest") != document_digest(policy_document):
            failures.append("policy digest does not match")

        for field in ("proposal_id", "candidate_kind", "objective", "artifact_path"):
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                failures.append(f"candidate {field} is blank")
        if candidate.get("evidence_contract_version") != 2:
            failures.append("candidate evidence contract version is unsupported")
        if candidate.get("candidate_kind") != _SCREENING_CANDIDATE_KIND:
            failures.append("candidate kind is not allowlisted")
        if candidate.get("artifact_path") != "backend/main.py":
            failures.append("candidate artifact path is not the warm-runtime implementation")
        for field in (
            "baseline_digest", "baseline_artifact_digest", "candidate_digest",
            "source_digest", "diff_digest",
        ):
            if not _screening_digest(candidate.get(field)):
                failures.append(f"candidate {field} is malformed")
        baseline_revision = candidate.get("baseline_source_revision")
        if (
            not isinstance(baseline_revision, str)
            or len(baseline_revision) not in {40, 64}
            or baseline_revision != baseline_revision.lower()
            or any(character not in "0123456789abcdef" for character in baseline_revision)
        ):
            failures.append("candidate baseline source revision is not a full Git commit OID")
        if candidate.get("candidate_digest") != candidate.get("source_digest"):
            failures.append("candidate digest is not the measured source digest")
        if candidate.get("baseline_artifact_digest") == candidate.get("candidate_digest"):
            failures.append("baseline and candidate artifacts must be distinct")
        if candidate.get("self_promotion_requested") is not False:
            failures.append("candidate requested self-promotion")
        diff_bytes = candidate.get("diff_bytes")
        if isinstance(diff_bytes, bool) or not isinstance(diff_bytes, int) or diff_bytes <= 0:
            unverifiable.append("candidate diff has no measurable bytes")
        try:
            current_digest = hashlib.sha256(Path(__file__).with_name("main.py").read_bytes()).hexdigest()
        except OSError:
            unverifiable.append("current warm-runtime artifact cannot be read")
        else:
            if current_digest != candidate.get("candidate_digest"):
                unverifiable.append("candidate artifact no longer matches current backend/main.py")

        baseline_artifact = extension.get("baseline_artifact")
        if not isinstance(baseline_artifact, Mapping):
            failures.append("replayable baseline artifact metadata is malformed")
        else:
            expected_baseline_metadata = {
                "artifact_path": "backend/main.py",
                "source_revision": baseline_revision,
                "artifact_digest": candidate.get("baseline_artifact_digest"),
            }
            if dict(baseline_artifact) != expected_baseline_metadata:
                failures.append("replayable baseline artifact metadata does not match")
            try:
                from .improvement_candidate import load_warm_runtime_baseline_artifact

                derived_baseline = load_warm_runtime_baseline_artifact(
                    Path(__file__).resolve().parents[1],
                    source_revision=(
                        baseline_revision if isinstance(baseline_revision, str) else ""
                    ),
                )
            except Exception:
                failures.append("immutable Git baseline could not be independently derived")
            else:
                if derived_baseline != expected_baseline_metadata:
                    failures.append("immutable Git baseline provenance does not match")

        comparison = measurement.get("comparison")
        baseline_observation: Mapping[str, Any] | None = None
        current_observation: Mapping[str, Any] | None = None
        if not isinstance(comparison, Mapping):
            failures.append("paired comparison evidence is malformed")
        else:
            if comparison.get("status") != "paired-replayable":
                failures.append("paired baseline was not replayable")
            if comparison.get("baseline_replayable") is not True:
                failures.append("paired baseline must be explicitly replayable")
            suite = comparison.get("suite")
            suite = suite if isinstance(suite, Mapping) else {}
            if (
                suite.get("id") != _SCREENING_SUITE_ID
                or suite.get("kind") != "fixed-public-contract"
                or suite.get("heldout") is not False
                or suite.get("test_count") != 5
            ):
                failures.append("paired comparison suite metadata is invalid")
            comparison_digest = comparison.get("comparison_digest")
            if not _screening_digest(comparison_digest) or comparison_digest != _screening_digest_value(
                _screening_without_digest(comparison, "comparison_digest")
            ):
                failures.append("comparison digest does not match")
            observations = comparison.get("retained_observations")
            baseline_observation = (
                observations.get("baseline") if isinstance(observations, Mapping) else None
            )
            current_observation = (
                observations.get("candidate") if isinstance(observations, Mapping) else None
            )
            if not isinstance(baseline_observation, Mapping) or not isinstance(
                current_observation, Mapping
            ):
                failures.append("paired comparison observations are malformed")
            else:
                if baseline_observation.get("artifact_digest") != candidate.get(
                    "baseline_artifact_digest"
                ):
                    failures.append("baseline score is not bound to the replayed artifact")
                if current_observation.get("artifact_digest") != candidate.get(
                    "candidate_digest"
                ):
                    failures.append("candidate score is not bound to the current artifact")
                if any(
                    observation.get("measurement_source")
                    != expected_measurement_source
                    for observation in (baseline_observation, current_observation)
                ):
                    failures.append("paired scores have an unsupported measurement source")
            if comparison.get("current_candidate") != current_observation:
                failures.append("current candidate observation does not match the paired score")

        reproducibility = measurement.get("reproducibility")
        evidence = extension.get("evidence_summary")
        image_digest = isolation.get("image_digest")
        if not isinstance(reproducibility, Mapping):
            failures.append("public reproduction record is malformed")
            baseline_runs: Any = None
            runs: Any = None
        else:
            if reproducibility.get("suite_id") != _SCREENING_SUITE_ID:
                failures.append("public reproduction used an unexpected suite")
            if (
                reproducibility.get("suite_kind") != "fixed-public-contract"
                or reproducibility.get("heldout") is not False
            ):
                failures.append("public reproduction is mislabeled as held-out")
            if reproducibility.get("required_runs") != required_probe_runs:
                failures.append("public reproduction did not require the accepted probe count")
            baseline_runs = reproducibility.get("baseline_runs")
            runs = reproducibility.get("runs")
            if reproducibility.get("baseline_replayed") is not True:
                failures.append("baseline reproduction was not completed")
            if reproducibility.get("all_passed") is not True:
                failures.append("candidate reproduction did not pass")

        baseline_runs_valid = _screening_phase_runs_valid(
            baseline_runs,
            "baseline",
            required_probe_runs,
            image_digest,
        )
        candidate_runs_valid = _screening_phase_runs_valid(
            runs,
            "candidate",
            required_probe_runs,
            image_digest,
        )
        if not baseline_runs_valid:
            failures.append(
                f"{required_probe_runs} canonical baseline probe records were not reproduced"
            )
        if not candidate_runs_valid or not all(
            run.get("passed") is True for run in runs if isinstance(run, Mapping)
        ):
            failures.append(
                f"{required_probe_runs} canonical candidate probe records were not reproduced"
            )
        if extension.get("baseline_probe_runs") != baseline_runs:
            failures.append("receipt baseline probe records do not match signed evidence")
        if extension.get("probe_runs") != runs:
            failures.append("receipt candidate probe records do not match signed evidence")

        if not _screening_observation_matches(
            baseline_observation,
            baseline_runs,
            candidate.get("baseline_artifact_digest"),
        ):
            failures.append(
                f"baseline score is not derived from its {required_probe_runs} probe records"
            )
        if not _screening_observation_matches(
            current_observation, runs, candidate.get("candidate_digest")
        ):
            failures.append(
                f"candidate score is not derived from its {required_probe_runs} probe records"
            )

        derived_improved = False
        if baseline_runs_valid and candidate_runs_valid:
            baseline_score = sum(
                1 for run in baseline_runs if run.get("passed") is True
            ) / len(baseline_runs)
            candidate_score = sum(
                1 for run in runs if run.get("passed") is True
            ) / len(runs)
            derived_improved = (
                candidate.get("baseline_artifact_digest")
                != candidate.get("candidate_digest")
                and candidate_score > baseline_score
            )
        if isinstance(comparison, Mapping):
            if comparison.get("improved") is not derived_improved:
                failures.append("paired improvement claim does not match derived scores")
            expected_qualification = (
                "measured-improvement" if derived_improved else "no-measured-improvement"
            )
            if comparison.get("qualification") != expected_qualification:
                failures.append("paired comparison qualification does not match derived scores")
        if not derived_improved:
            unverifiable.append("candidate did not measurably improve the paired baseline")

        if any(isolation.get(field) is not True for field in (
            "sandboxed", "network_default_deny", "bounded_resources"
        )):
            failures.append("candidate isolation evidence is incomplete")
        if isolation.get("image_tag_inspected") != "obus-dev:latest" or not _screening_digest(image_digest):
            failures.append("Docker image inspection evidence is invalid")
        if isolation.get("executed_image_ref") != f"sha256:{image_digest}":
            failures.append("candidate probes did not execute the inspected immutable image")

        residency = measurement.get("residency")
        if not isinstance(residency, Mapping):
            failures.append("Ollama residency observation is malformed")
        else:
            residency_digest = residency.get("observation_digest")
            if not _screening_digest(residency_digest) or residency_digest != _screening_digest_value(
                _screening_without_digest(residency, "observation_digest")
            ):
                failures.append("Ollama residency observation digest does not match")
            if residency.get("model") != _SCREENING_MODEL:
                failures.append("residency observed the wrong model")
            requested = residency.get("requested_context", residency.get("num_ctx"))
            if requested != _SCREENING_CONTEXT:
                failures.append("residency requested the wrong context window")
            observed = residency.get("observed_context")
            if isinstance(observed, bool) or not isinstance(observed, int) or observed < _SCREENING_CONTEXT:
                failures.append("residency did not observe the required context window")
            if (
                residency.get("generation_done") is not True
                or residency.get("resident") is not True
                or residency.get("verified") is not True
            ):
                failures.append("live Ollama generation and residency were not both verified")
        if extension.get("residency") != residency:
            failures.append("receipt residency record does not match signed evidence")

        binding = extension.get("binding")
        if not isinstance(binding, Mapping) or any(
            binding.get(field) != candidate.get(field)
            for field in (
                "proposal_id", "baseline_digest", "baseline_source_revision",
                "baseline_artifact_digest", "candidate_digest",
            )
        ):
            failures.append("candidate receipt binding does not match")
        if not isinstance(evidence, Mapping):
            failures.append("candidate evidence summary is malformed")
        else:
            for field in (
                "baseline_artifact_digest", "source_digest", "diff_digest",
                "image_digest", "test_digest", "evaluator_digest",
                "baseline_command_digest", "command_digest",
                "baseline_output_digest", "output_digest",
                "harness_manifest_digest", "baseline_manifest_digest",
                "candidate_manifest_digest",
            ):
                if not _screening_digest(evidence.get(field)):
                    failures.append(f"candidate evidence {field} is malformed")
            if (
                evidence.get("baseline_probe_runs") != required_probe_runs
                or evidence.get("probe_runs") != required_probe_runs
            ):
                failures.append("candidate evidence probe counts do not match the accepted receipt")
            if counterbalanced and evidence.get("arm_execution_order") != [
                "baseline", "candidate", "candidate", "baseline"
            ]:
                failures.append("candidate evidence counterbalanced schedule is not exact")
            harness_manifest = evidence.get("harness_manifest")
            baseline_manifest = evidence.get("baseline_manifest")
            candidate_manifest = evidence.get("candidate_manifest")
            if not all(
                isinstance(manifest, Mapping)
                for manifest in (harness_manifest, baseline_manifest, candidate_manifest)
            ):
                failures.append("paired artifact manifests are malformed")
            else:
                if (
                    evidence.get("harness_manifest_digest")
                    != _screening_digest_value(harness_manifest)
                    or evidence.get("baseline_manifest_digest")
                    != _screening_digest_value(baseline_manifest)
                    or evidence.get("candidate_manifest_digest")
                    != _screening_digest_value(candidate_manifest)
                ):
                    failures.append("paired artifact manifest digest does not match")
                if (
                    harness_manifest.get("schema_version") != 1
                    or harness_manifest.get("candidate_kind")
                    != _SCREENING_CANDIDATE_KIND
                    or harness_manifest.get("sandbox_kind")
                    != "docker-network-none-read-only"
                    or harness_manifest.get("image_digest") != image_digest
                    or harness_manifest.get("executed_image_ref")
                    != isolation.get("executed_image_ref")
                    or harness_manifest.get("command_digest")
                    != evidence.get("command_digest")
                    or harness_manifest.get("probe_runs") != required_probe_runs
                    or harness_manifest.get("test_digest")
                    != evidence.get("test_digest")
                    or harness_manifest.get("evaluator_digest")
                    != evidence.get("evaluator_digest")
                    or harness_manifest.get("model") != _SCREENING_MODEL
                    or harness_manifest.get("requested_context")
                    != _SCREENING_CONTEXT
                ):
                    failures.append("paired harness manifest contract does not match")
                if counterbalanced and (
                    harness_manifest.get("arm_execution_order")
                    != ["baseline", "candidate", "candidate", "baseline"]
                    or harness_manifest.get("probe_runs_per_block") != 3
                ):
                    failures.append("counterbalanced harness schedule is not exact")
                expected_baseline_manifest = {
                    "schema_version": 1,
                    "phase": "baseline",
                    "artifact_path": "backend/main.py",
                    "source_revision": baseline_revision,
                    "artifact_digest": candidate.get("baseline_artifact_digest"),
                    "harness_manifest_digest": evidence.get(
                        "harness_manifest_digest"
                    ),
                }
                expected_candidate_manifest = {
                    "schema_version": 1,
                    "phase": "candidate",
                    "artifact_path": "backend/main.py",
                    "artifact_digest": candidate.get("candidate_digest"),
                    "harness_manifest_digest": evidence.get(
                        "harness_manifest_digest"
                    ),
                }
                if dict(baseline_manifest) != expected_baseline_manifest:
                    failures.append("baseline artifact manifest does not match")
                if dict(candidate_manifest) != expected_candidate_manifest:
                    failures.append("candidate artifact manifest does not match")
            if evidence.get("evidence_contract_version") != 2:
                failures.append("candidate evidence contract is not bound to signed evidence")
            if evidence.get("objective") != candidate.get("objective"):
                failures.append("candidate objective is not bound to signed evidence")
            if evidence.get("baseline_source_revision") != baseline_revision:
                failures.append("baseline source revision is not bound to signed evidence")
            if evidence.get("baseline_artifact_digest") != candidate.get(
                "baseline_artifact_digest"
            ):
                failures.append("baseline artifact is not bound to signed evidence")
            if evidence.get("source_digest") != candidate.get("source_digest"):
                failures.append("candidate source is not bound to signed evidence")
            if evidence.get("diff_digest") != candidate.get("diff_digest") or evidence.get("diff_bytes") != diff_bytes:
                failures.append("candidate diff is not bound to signed evidence")
            if evidence.get("image_digest") != image_digest or evidence.get("executed_image_ref") != isolation.get("executed_image_ref"):
                failures.append("candidate image is not bound to signed evidence")
            baseline_command_digests = (
                {
                    run.get("command_digest")
                    for run in baseline_runs
                    if isinstance(run, Mapping)
                }
                if isinstance(baseline_runs, list)
                else set()
            )
            run_command_digests = (
                {
                    run.get("command_digest")
                    for run in runs
                    if isinstance(run, Mapping)
                }
                if isinstance(runs, list)
                else set()
            )
            if baseline_command_digests != {evidence.get("baseline_command_digest")}:
                failures.append("baseline command digest is not bound to every probe record")
            if run_command_digests != {evidence.get("command_digest")}:
                failures.append("candidate command digest is not bound to every probe record")
            if evidence.get("baseline_command_digest") != evidence.get("command_digest"):
                failures.append("paired probes did not use the same sealed command manifest")
            if evidence.get("baseline_output_digest") != _screening_digest_value(
                baseline_runs
            ):
                failures.append("baseline output digest does not bind the probe records")
            if evidence.get("output_digest") != _screening_digest_value(runs):
                failures.append("candidate output digest does not bind the probe records")
            if evidence.get("comparison") != comparison:
                failures.append("candidate comparison is not bound to signed evidence")
            if evidence.get("residency_observation_digest") != (residency.get("observation_digest") if isinstance(residency, Mapping) else None):
                failures.append("candidate residency digest is not bound to signed evidence")
        if governance.get("policy_boundary_changed") is not False:
            failures.append("candidate changed the policy boundary")
        if governance.get("human_authorization") != {"status": "pending"}:
            failures.append("human authorization must be explicitly pending")
        if governance.get("autonomous_promotion_permitted") is not False:
            failures.append("screening receipt attempted to permit autonomous promotion")
        if rollback.get("checkpoint_digest") != candidate.get("baseline_digest"):
            failures.append("rollback checkpoint is not bound to the loop baseline")
        if rollback.get("restore_status") != "not-measured":
            failures.append("screening receipt made an unsupported rollback claim")
        failures.extend(_screening_attestation_failures(extension))

    status = "fail" if failures else ("incomplete" if missing or unverifiable else "pass")
    decision = {
        "pass": "ready-for-human-authorization",
        "fail": "rejected",
        "incomplete": "insufficient-evidence",
    }[status]
    return {
        "overall_status": status,
        "decision": decision,
        "promotion_authorized": False,
        "human_authorization_status": "pending",
        "policy_id": policy_document["policy"]["id"],
        "policy_version": policy_document["policy"]["version"],
        "policy_digest": document_digest(policy_document),
        "missing_fields": missing,
        "unverifiable_fields": unverifiable,
        "failed_checks": failures,
        "checks": {
            "measured_comparison_complete": not any("comparison" in item or "artifact" in item for item in missing + unverifiable + failures),
            "public_reproduction_complete": not any("reproduction" in item or "probe" in item for item in missing + failures),
            "residency_verified": not any("residency" in item or "Ollama" in item for item in missing + failures),
            "human_authorization_pending": _screening_path(receipt, "governance.human_authorization.status") == "pending",
        },
    }


class ImprovementEvaluationError(ValueError):
    """Raised when the policy itself is invalid or cannot be loaded."""


def document_digest(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_policy(policy: Mapping[str, Any]) -> None:
    """Validate the policy envelope before it can judge a receipt."""

    if policy.get("schema_version") != 1:
        raise ImprovementEvaluationError("unsupported improvement policy schema")
    metadata = policy.get("policy")
    if not isinstance(metadata, Mapping):
        raise ImprovementEvaluationError("improvement policy metadata is missing")
    if metadata.get("id") != "obus-guarded-self-improvement":
        raise ImprovementEvaluationError("unexpected improvement policy id")
    if not isinstance(metadata.get("version"), str) or not metadata.get("version"):
        raise ImprovementEvaluationError("improvement policy version is missing")
    requirements = policy.get("promotion_requirements")
    if not isinstance(requirements, Mapping):
        raise ImprovementEvaluationError("promotion requirements are missing")
    minimum_delta = requirements.get("minimum_candidate_delta")
    minimum_runs = requirements.get("minimum_reproducible_runs")
    if not isinstance(minimum_delta, (int, float)) or not 0 <= minimum_delta <= 1:
        raise ImprovementEvaluationError("minimum candidate delta is invalid")
    if not isinstance(minimum_runs, int) or minimum_runs < 1:
        raise ImprovementEvaluationError("minimum reproducible runs is invalid")
    authority = policy.get("authority")
    if not isinstance(authority, Mapping):
        raise ImprovementEvaluationError("authority policy is missing")
    if "authorize-promotion" not in authority.get("human_only_actions", []):
        raise ImprovementEvaluationError("promotion authority must remain human-only")


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the versioned improvement policy."""

    policy_path = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImprovementEvaluationError(
            f"unable to load improvement policy: {exc}"
        ) from exc
    if not isinstance(policy, dict):
        raise ImprovementEvaluationError("improvement policy must be an object")
    validate_policy(policy)
    return policy


def _dig(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _is_digest(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class _ReceiptChecker:
    def __init__(self, receipt: Mapping[str, Any]) -> None:
        self.receipt = receipt
        self.checks: list[dict[str, str]] = []

    def get(self, path: str) -> Any:
        return _dig(self.receipt, path)

    def add(
        self,
        check_id: str,
        value: Any,
        predicate: bool,
        passed_detail: str,
        failed_detail: str,
    ) -> None:
        if value is _MISSING:
            self.checks.append(
                {
                    "id": check_id,
                    "status": "incomplete",
                    "detail": "required evidence is missing",
                }
            )
            return
        self.checks.append(
            {
                "id": check_id,
                "status": "passed" if predicate else "failed",
                "detail": passed_detail if predicate else failed_detail,
            }
        )

    def expect(self, path: str, expected: Any, detail: str) -> Any:
        value = self.get(path)
        self.add(path, value, value == expected, detail, f"expected {expected!r}")
        return value

    def require_text(self, path: str, detail: str) -> Any:
        value = self.get(path)
        self.add(
            path,
            value,
            isinstance(value, str) and bool(value.strip()),
            detail,
            "must be a non-empty string",
        )
        return value

    def require_digest(self, path: str) -> Any:
        value = self.get(path)
        self.add(
            path,
            value,
            _is_digest(value),
            "content digest is present",
            "must be a 64-character SHA-256 digest",
        )
        return value


def _check_candidate(checker: _ReceiptChecker) -> tuple[Any, Any]:
    proposal_id = checker.require_text(
        "candidate.proposal_id", "proposal identity is present"
    )
    checker.require_text("candidate.objective", "candidate objective is declared")
    proposer_id = checker.require_text(
        "candidate.proposer_id", "candidate proposer identity is present"
    )
    baseline_digest = checker.require_digest("candidate.baseline_digest")
    candidate_digest = checker.require_digest("candidate.candidate_digest")
    checker.require_digest("candidate.diff_digest")
    checker.require_digest("candidate.source_tree_digest")
    if baseline_digest is _MISSING or candidate_digest is _MISSING:
        checker.add(
            "candidate.changed",
            _MISSING,
            False,
            "candidate differs from the baseline",
            "candidate and baseline digests must differ",
        )
    else:
        checker.add(
            "candidate.changed",
            candidate_digest,
            _is_digest(baseline_digest)
            and _is_digest(candidate_digest)
            and baseline_digest != candidate_digest,
            "candidate differs from the baseline",
            "candidate and baseline digests must be valid and different",
        )
    checker.expect(
        "candidate.self_promotion_requested",
        False,
        "candidate did not request self-promotion",
    )
    return proposal_id, proposer_id


def _check_isolation(checker: _ReceiptChecker) -> None:
    checker.expect("isolation.sandboxed", True, "candidate ran in a sandbox")
    checker.expect(
        "isolation.network_default_deny",
        True,
        "sandbox network access was denied by default",
    )
    checker.expect(
        "isolation.bounded_resources",
        True,
        "sandbox resource bounds were enforced",
    )


def _check_evaluator(checker: _ReceiptChecker, proposer_id: Any) -> None:
    checker.require_digest("evaluator.evaluator_digest")
    checker.require_digest("evaluator.public_suite_digest")
    checker.require_digest("evaluator.heldout_suite_digest")
    checker.expect(
        "evaluator.frozen_before_proposal",
        True,
        "evaluator was frozen before proposal creation",
    )
    checker.expect(
        "evaluator.candidate_modified_evaluator",
        False,
        "candidate did not modify the evaluator",
    )
    checker.expect(
        "evaluator.candidate_accessed_heldout",
        False,
        "candidate did not access held-out tests or answers",
    )
    verifier_id = checker.require_text(
        "evaluator.independent_verifier_id", "independent verifier is identified"
    )
    if proposer_id is _MISSING or verifier_id is _MISSING:
        checker.add(
            "evaluator.independent_verifier",
            _MISSING,
            False,
            "verifier is independent from the candidate proposer",
            "independent verifier identity is required",
        )
        return
    checker.add(
        "evaluator.independent_verifier",
        verifier_id,
        bool(proposer_id) and bool(verifier_id) and proposer_id != verifier_id,
        "verifier is independent from the candidate proposer",
        "candidate proposer cannot be its own verifier",
    )


def _check_results(
    checker: _ReceiptChecker, requirements: Mapping[str, Any]
) -> None:
    baseline_score = checker.get("results.baseline_score")
    candidate_score = checker.get("results.candidate_score")
    minimum_delta = requirements["minimum_candidate_delta"]
    if baseline_score is _MISSING or candidate_score is _MISSING:
        checker.add(
            "results.objective_delta",
            _MISSING,
            False,
            "candidate clears the frozen improvement threshold",
            "baseline and candidate scores are required",
        )
    else:
        valid_scores = (
            _is_number(baseline_score)
            and _is_number(candidate_score)
            and 0 <= baseline_score <= 1
            and 0 <= candidate_score <= 1
        )
        checker.add(
            "results.objective_delta",
            candidate_score,
            valid_scores and candidate_score - baseline_score >= minimum_delta,
            f"candidate improves the frozen score by at least {minimum_delta:.2f}",
            "scores must be normalized to 0..1 and clear the frozen minimum delta",
        )
    for suite_result in requirements["required_suite_results"]:
        checker.expect(
            f"results.{suite_result}",
            True,
            suite_result.replace("_", " "),
        )
    reproducible_runs = checker.get("results.reproducible_runs")
    minimum_runs = requirements["minimum_reproducible_runs"]
    checker.add(
        "results.reproducible_runs",
        reproducible_runs,
        isinstance(reproducible_runs, int)
        and not isinstance(reproducible_runs, bool)
        and reproducible_runs >= minimum_runs,
        f"candidate reproduced across at least {minimum_runs} runs",
        f"at least {minimum_runs} reproducible runs are required",
    )


def _check_governance(
    checker: _ReceiptChecker,
    proposal_id: Any,
    requirements: Mapping[str, Any],
) -> None:
    checker.expect(
        "governance.policy_boundary_changed",
        False,
        "candidate did not change its policy boundary",
    )
    checker.expect(
        "governance.critical_incidents",
        requirements["maximum_critical_incidents"],
        "candidate recorded no critical incident",
    )
    checker.require_text(
        "governance.human_authorization.approval_id",
        "human approval receipt is present",
    )
    checker.require_digest("governance.human_authorization.approval_digest")
    checker.require_text(
        "governance.human_authorization.approver_id",
        "human approver identity is present",
    )
    checker.expect(
        "governance.human_authorization.approver_kind",
        "human",
        "promotion approver is human",
    )
    checker.expect(
        "governance.human_authorization.independent_from_candidate",
        True,
        "human approver is independent from the candidate",
    )
    checker.expect(
        "governance.human_authorization.action",
        "authorize-promotion",
        "authorization is scoped to promotion",
    )
    expected_scope = (
        f"promote:{proposal_id}" if isinstance(proposal_id, str) else _MISSING
    )
    scope = checker.get("governance.human_authorization.scope")
    checker.add(
        "governance.human_authorization.scope",
        scope,
        expected_scope is not _MISSING and scope == expected_scope,
        "authorization is bound to this proposal",
        "authorization scope must be bound to the proposal id",
    )


def _check_recovery_and_monitoring(checker: _ReceiptChecker) -> None:
    checker.require_text("rollback.checkpoint_id", "rollback checkpoint is identified")
    checker.require_digest("rollback.checkpoint_digest")
    checker.expect("rollback.restore_tested", True, "rollback restore was tested")
    checker.expect(
        "monitoring.canary_required", True, "post-promotion canary is required"
    )
    checker.expect(
        "monitoring.rollback_trigger_defined",
        True,
        "automatic rollback trigger is defined",
    )
    checker.expect(
        "monitoring.post_promotion_checks_defined",
        True,
        "post-promotion checks are defined",
    )


def evaluate_improvement_receipt(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one improvement receipt without causing any runtime mutation."""

    if not isinstance(receipt, Mapping):
        raise ImprovementEvaluationError("improvement receipt must be an object")
    active_policy = dict(policy) if policy is not None else load_policy()
    validate_policy(active_policy)
    metadata = active_policy["policy"]
    requirements = active_policy["promotion_requirements"]
    policy_digest = document_digest(active_policy)
    checker = _ReceiptChecker(receipt)

    checker.expect("schema_version", 1, "receipt schema matches")
    checker.expect("policy_id", metadata["id"], "policy identity matches")
    checker.expect("policy_version", metadata["version"], "policy version matches")
    checker.expect("policy_digest", policy_digest, "policy digest matches")
    proposal_id, proposer_id = _check_candidate(checker)
    _check_isolation(checker)
    _check_evaluator(checker, proposer_id)
    _check_results(checker, requirements)
    _check_governance(checker, proposal_id, requirements)
    _check_recovery_and_monitoring(checker)

    statuses = [check["status"] for check in checker.checks]
    if "failed" in statuses:
        overall_status, decision = "failed", "reject"
    elif "incomplete" in statuses:
        overall_status, decision = "incomplete", "incomplete"
    else:
        overall_status, decision = "passed", "authorized-for-promotion"
    blockers = [
        check["id"] for check in checker.checks if check["status"] != "passed"
    ]

    return {
        "schema_version": 1,
        "policy_id": metadata["id"],
        "policy_version": metadata["version"],
        "policy_digest": policy_digest,
        "receipt_digest": document_digest(dict(receipt)),
        "overall_status": overall_status,
        "decision": decision,
        "promotion_authorized": overall_status == "passed",
        "autonomous_promotion_permitted": False,
        "human_authorization_required": True,
        "policy_statement": metadata["statement"],
        "blockers": blockers,
        "checks": checker.checks,
    }
