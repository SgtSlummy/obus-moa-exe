"""Fail-closed evaluator for the Obus Autonomous AGI claim contract.

This module does not run benchmarks and it never infers capability from ordinary
Obus receipts. It evaluates a sealed qualification receipt against the
versioned manifest in ``data/autonomous-agi-evaluation-manifest.json``.
Missing, malformed, stale, contaminated, or fallback-routed evidence cannot
produce a passing screen. Self-submitted receipts can reach candidate status but
cannot authorize the claim; artifact rehashing and authenticated independent
attestation remain external to this screening module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "autonomous-agi-evaluation-manifest.json"
)
_ALLOWED_OPERATORS = {"eq", "gte", "lte"}
_ALLOWED_STATUSES = {"passed", "failed", "incomplete"}
_MISSING = object()


class AGIEvaluationError(ValueError):
    """Raised when the claim manifest itself is invalid."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def document_digest(value: Any) -> str:
    """Return the SHA-256 digest of a JSON-compatible value."""

    return hashlib.sha256(_canonical_json(value)).hexdigest()


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path) if path is not None else DEFAULT_MANIFEST_PATH
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AGIEvaluationError(f"Unable to load AGI manifest: {exc}") from exc
    validate_manifest(payload)
    return payload


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AGIEvaluationError(f"{label} must be an object")
    return value


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AGIEvaluationError(f"{label} must be a non-empty string")
    return value


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Validate the trusted contract before evaluating untrusted receipts."""

    root = _require_mapping(manifest, "manifest")
    schema_version = root.get("schema_version")
    if schema_version not in {1, 2}:
        raise AGIEvaluationError("manifest.schema_version must equal 1 or 2")

    claim = _require_mapping(root.get("claim"), "manifest.claim")
    for key in ("id", "version", "definition", "qualified_statement"):
        _require_nonempty_string(claim.get(key), f"manifest.claim.{key}")
    current_level = _require_nonempty_string(
        claim.get("current_level"), "manifest.claim.current_level"
    )
    expected_target = "A4" if schema_version == 1 else "A23"
    if claim.get("target_level") != expected_target:
        raise AGIEvaluationError(
            f"manifest.claim.target_level must equal {expected_target} for schema v{schema_version}"
        )
    if schema_version == 2 and current_level not in {"A0", "A1", "A2", "A3"}:
        raise AGIEvaluationError(
            "manifest.claim.current_level must be a pre-A23 verified level"
        )
    if schema_version == 2:
        if claim.get("gate_count") != 23:
            raise AGIEvaluationError("manifest.claim.gate_count must equal 23 for A23")
        if claim.get("receipt_schema_version") != 2:
            raise AGIEvaluationError(
                "manifest.claim.receipt_schema_version must equal 2 for A23"
            )

    policy = _require_mapping(root.get("evidence_policy"), "manifest.evidence_policy")
    for key in (
        "required_primary_runs",
        "required_independent_replications",
        "max_evidence_age_days",
    ):
        value = policy.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise AGIEvaluationError(f"manifest.evidence_policy.{key} must be a positive integer")
    sealed_fraction = policy.get("minimum_sealed_task_fraction")
    if not _is_number(sealed_fraction) or not 0 <= float(sealed_fraction) <= 1:
        raise AGIEvaluationError(
            "manifest.evidence_policy.minimum_sealed_task_fraction must be between 0 and 1"
        )
    if schema_version == 2:
        independent_organizations = policy.get("minimum_independent_organizations")
        if (
            not isinstance(independent_organizations, int)
            or isinstance(independent_organizations, bool)
            or independent_organizations < 1
        ):
            raise AGIEvaluationError(
                "manifest.evidence_policy.minimum_independent_organizations must be positive"
            )
        if policy.get("minimum_passed_gate_count") != 23:
            raise AGIEvaluationError(
                "manifest.evidence_policy.minimum_passed_gate_count must equal 23"
            )
        if policy.get("required_primary_runs") != 3:
            raise AGIEvaluationError(
                "manifest.evidence_policy.required_primary_runs must equal 3 for A23"
            )
        if policy.get("required_independent_replications") != 1:
            raise AGIEvaluationError(
                "manifest.evidence_policy.required_independent_replications must equal 1 for A23"
            )
        for key in (
            "self_certification_permitted",
            "api_submissions_can_authorize",
        ):
            if policy.get(key) is not False:
                raise AGIEvaluationError(
                    f"manifest.evidence_policy.{key} must be false"
                )
        for key in (
            "external_artifact_rehash_required",
            "authenticated_independent_attestation_required",
        ):
            if policy.get(key) is not True:
                raise AGIEvaluationError(
                    f"manifest.evidence_policy.{key} must be true"
                )
    for key in ("required_identity_paths", "frozen_identity_paths", "required_artifact_kinds"):
        values = policy.get(key)
        if not isinstance(values, list) or not values:
            raise AGIEvaluationError(f"manifest.evidence_policy.{key} must be a non-empty list")
        if any(not isinstance(item, str) or not item for item in values):
            raise AGIEvaluationError(f"manifest.evidence_policy.{key} contains an invalid value")

    gates = root.get("gates")
    if not isinstance(gates, list) or not gates:
        raise AGIEvaluationError("manifest.gates must be a non-empty list")
    expected_gate_count = 11 if schema_version == 1 else 23
    if len(gates) != expected_gate_count:
        raise AGIEvaluationError(
            f"manifest.gates must contain exactly {expected_gate_count} gates for schema v{schema_version}"
        )
    gate_ids: set[str] = set()
    for gate_index, gate_value in enumerate(gates):
        gate = _require_mapping(gate_value, f"manifest.gates[{gate_index}]")
        gate_id = _require_nonempty_string(gate.get("id"), f"manifest.gates[{gate_index}].id")
        if gate_id in gate_ids:
            raise AGIEvaluationError(f"duplicate gate id: {gate_id}")
        gate_ids.add(gate_id)
        for key in (
            "title",
            "source_defined_metric",
            "obus_normative_threshold",
            "threshold_provenance",
        ):
            _require_nonempty_string(gate.get(key), f"manifest.gates[{gate_index}].{key}")
        if gate.get("threshold_provenance") not in {"source-defined", "obus-policy", "mixed"}:
            raise AGIEvaluationError(
                f"manifest.gates[{gate_index}].threshold_provenance is invalid"
            )
        sources = gate.get("sources")
        if not isinstance(sources, list) or not sources:
            raise AGIEvaluationError(f"manifest.gates[{gate_index}].sources must not be empty")
        for source_index, source_value in enumerate(sources):
            source = _require_mapping(
                source_value,
                f"manifest.gates[{gate_index}].sources[{source_index}]",
            )
            _require_nonempty_string(source.get("title"), "source.title")
            _require_nonempty_string(source.get("url"), "source.url")

        checks = gate.get("checks")
        if not isinstance(checks, list) or not checks:
            raise AGIEvaluationError(f"manifest.gates[{gate_index}].checks must not be empty")
        check_ids: set[str] = set()
        for check_index, check_value in enumerate(checks):
            check = _require_mapping(
                check_value,
                f"manifest.gates[{gate_index}].checks[{check_index}]",
            )
            check_id = _require_nonempty_string(check.get("id"), "check.id")
            if check_id in check_ids:
                raise AGIEvaluationError(f"duplicate check id in {gate_id}: {check_id}")
            check_ids.add(check_id)
            _require_nonempty_string(check.get("path"), "check.path")
            if check.get("operator") not in _ALLOWED_OPERATORS:
                raise AGIEvaluationError(f"invalid operator in {gate_id}.{check_id}")
            if "value" not in check:
                raise AGIEvaluationError(f"missing value in {gate_id}.{check_id}")
            _require_nonempty_string(check.get("threshold_origin"), "check.threshold_origin")
            if check.get("threshold_origin") not in {"source-defined", "obus-policy"}:
                raise AGIEvaluationError(f"invalid threshold_origin in {gate_id}.{check_id}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _lookup(value: Any, path: str) -> Any:
    current = value
    for component in path.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return _MISSING
        current = current[component]
    return current


def _status(check_id: str, status: str, detail: str, **extra: Any) -> dict[str, Any]:
    if status not in _ALLOWED_STATUSES:
        raise RuntimeError(f"unsupported evaluator status: {status}")
    result = {"id": check_id, "status": status, "detail": detail}
    result.update(extra)
    return result


def _aggregate_status(items: Sequence[Mapping[str, Any]]) -> str:
    statuses = {item.get("status") for item in items}
    if "failed" in statuses:
        return "failed"
    if "incomplete" in statuses or not items:
        return "incomplete"
    return "passed"


def _compare(actual: Any, operator: str, expected: Any) -> tuple[str, str]:
    if operator == "eq":
        if type(actual) is not type(expected):
            return "incomplete", "value has the wrong type"
        return ("passed", "value matches") if actual == expected else ("failed", "value does not match")
    if not _is_number(actual) or not _is_number(expected):
        return "incomplete", "ordered comparison requires finite numeric values"
    if operator == "gte":
        return ("passed", "value meets minimum") if actual >= expected else ("failed", "value is below minimum")
    if operator == "lte":
        return ("passed", "value meets maximum") if actual <= expected else ("failed", "value exceeds maximum")
    return "incomplete", "operator is unsupported"


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _run_structure_checks(
    run: Mapping[str, Any],
    *,
    label: str,
    manifest: Mapping[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    policy = manifest["evidence_policy"]
    results: list[dict[str, Any]] = []

    run_id = run.get("run_id")
    results.append(
        _status(
            f"{label}.run_id",
            "passed" if isinstance(run_id, str) and bool(run_id.strip()) else "incomplete",
            "run id is present" if isinstance(run_id, str) and run_id.strip() else "run id is missing",
        )
    )
    results.append(
        _status(
            f"{label}.completed",
            "passed" if run.get("status") == "completed" else "incomplete",
            "run completed" if run.get("status") == "completed" else "run is not completed",
        )
    )

    completed_at = _parse_time(run.get("completed_at"))
    if completed_at is None:
        results.append(_status(f"{label}.recency", "incomplete", "completed_at is missing or invalid"))
    elif completed_at > now + timedelta(minutes=5):
        results.append(_status(f"{label}.recency", "failed", "completed_at is implausibly in the future"))
    elif now - completed_at > timedelta(days=policy["max_evidence_age_days"]):
        results.append(_status(f"{label}.recency", "failed", "evidence is older than the allowed window"))
    else:
        results.append(_status(f"{label}.recency", "passed", "evidence is within the allowed window"))

    for path in policy["required_identity_paths"]:
        actual = _lookup(run, path)
        present = actual is not _MISSING and actual is not None and actual != ""
        results.append(
            _status(
                f"{label}.identity.{path}",
                "passed" if present else "incomplete",
                "identity is pinned" if present else "required identity is missing",
            )
        )

    fallback = _lookup(run, "subject.provider_fallback_used")
    fallback_status, fallback_detail = _compare(fallback, "eq", False) if fallback is not _MISSING else (
        "incomplete",
        "fallback evidence is missing",
    )
    results.append(_status(f"{label}.no_fallback", fallback_status, fallback_detail))

    memory_isolated = _lookup(run, "subject.memory_isolated")
    memory_status, memory_detail = _compare(memory_isolated, "eq", True) if memory_isolated is not _MISSING else (
        "incomplete",
        "memory-isolation evidence is missing",
    )
    results.append(_status(f"{label}.memory_isolated", memory_status, memory_detail))

    sealed = _lookup(run, "suite.sealed")
    sealed_status, sealed_detail = _compare(sealed, "eq", True) if sealed is not _MISSING else (
        "incomplete",
        "sealed-suite evidence is missing",
    )
    results.append(_status(f"{label}.sealed_suite", sealed_status, sealed_detail))

    contamination = _lookup(run, "suite.contamination_screen_passed")
    contamination_status, contamination_detail = (
        _compare(contamination, "eq", True)
        if contamination is not _MISSING
        else ("incomplete", "contamination-screen evidence is missing")
    )
    results.append(
        _status(f"{label}.contamination_screen", contamination_status, contamination_detail)
    )

    sealed_fraction = _lookup(run, "suite.sealed_task_fraction")
    if sealed_fraction is _MISSING:
        fraction_status, fraction_detail = "incomplete", "sealed task fraction is missing"
    else:
        fraction_status, fraction_detail = _compare(
            sealed_fraction,
            "gte",
            policy["minimum_sealed_task_fraction"],
        )
    results.append(_status(f"{label}.sealed_fraction", fraction_status, fraction_detail))

    verifier_fields = ("verifier.identity", "verifier.method_digest", "verifier.result_digest")
    for path in verifier_fields:
        actual = _lookup(run, path)
        present = actual is not _MISSING and isinstance(actual, str) and bool(actual.strip())
        results.append(
            _status(
                f"{label}.{path}",
                "passed" if present else "incomplete",
                "verifier evidence is present" if present else "verifier evidence is missing",
            )
        )
    independent_verifier = _lookup(run, "verifier.independent_of_subject")
    verifier_status, verifier_detail = (
        _compare(independent_verifier, "eq", True)
        if independent_verifier is not _MISSING
        else ("incomplete", "verifier independence is missing")
    )
    results.append(_status(f"{label}.verifier_independence", verifier_status, verifier_detail))

    incidents = run.get("critical_incidents", _MISSING)
    if incidents is _MISSING or not isinstance(incidents, list):
        results.append(_status(f"{label}.critical_incidents", "incomplete", "critical incident ledger is missing"))
    elif incidents:
        results.append(_status(f"{label}.critical_incidents", "failed", "critical incidents were recorded"))
    else:
        results.append(_status(f"{label}.critical_incidents", "passed", "no critical incidents were recorded"))

    artifacts = run.get("artifacts")
    artifacts_by_kind: dict[str, Mapping[str, Any]] = {}
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, Mapping) and isinstance(artifact.get("kind"), str):
                artifacts_by_kind[artifact["kind"]] = artifact
    for kind in policy["required_artifact_kinds"]:
        artifact = artifacts_by_kind.get(kind)
        valid = bool(
            artifact
            and isinstance(artifact.get("uri"), str)
            and artifact.get("uri")
            and isinstance(artifact.get("sha256"), str)
            and len(artifact["sha256"]) == 64
            and all(character in "0123456789abcdef" for character in artifact["sha256"].lower())
        )
        results.append(
            _status(
                f"{label}.artifact.{kind}",
                "passed" if valid else "incomplete",
                "artifact is hash-addressed" if valid else "required hash-addressed artifact is missing",
            )
        )
    return results


def _gate_result(
    gate: Mapping[str, Any],
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not runs:
        return {
            "id": gate["id"],
            "title": gate["title"],
            "status": "incomplete",
            "threshold_provenance": gate["threshold_provenance"],
            "detail": "no eligible runs were supplied",
            "checks": [],
        }

    for run_index, run in enumerate(runs):
        label = run.get("run_id") if isinstance(run.get("run_id"), str) else f"run-{run_index + 1}"
        metrics = run.get("metrics")
        for check in gate["checks"]:
            actual = _lookup(metrics, check["path"]) if isinstance(metrics, Mapping) else _MISSING
            if actual is _MISSING:
                check_status, detail = "incomplete", "metric is missing"
                actual_for_output: Any = None
            else:
                check_status, detail = _compare(actual, check["operator"], check["value"])
                actual_for_output = actual
            checks.append(
                {
                    "id": check["id"],
                    "run_id": label,
                    "status": check_status,
                    "detail": detail,
                    "path": check["path"],
                    "operator": check["operator"],
                    "expected": check["value"],
                    "actual": actual_for_output,
                    "threshold_origin": check["threshold_origin"],
                }
            )
    status = _aggregate_status(checks)
    return {
        "id": gate["id"],
        "title": gate["title"],
        "status": status,
        "threshold_provenance": gate["threshold_provenance"],
        "detail": "all run-level checks passed" if status == "passed" else "one or more run-level checks did not pass",
        "checks": checks,
    }


def _receipt_header_checks(
    receipt: Mapping[str, Any],
    claim: Mapping[str, Any],
    manifest_sha: str,
) -> tuple[list[dict[str, Any]], Any]:
    checks: list[dict[str, Any]] = []
    for check_id, actual, expected in (
        (
            "receipt.schema_version",
            receipt.get("schema_version"),
            claim.get("receipt_schema_version", 1),
        ),
        ("receipt.claim_id", receipt.get("claim_id"), claim["id"]),
        ("receipt.claim_version", receipt.get("claim_version"), claim["version"]),
        ("receipt.manifest_digest", receipt.get("manifest_digest"), manifest_sha),
    ):
        if actual is None:
            checks.append(_status(check_id, "incomplete", "required receipt field is missing"))
        else:
            check_status, detail = _compare(actual, "eq", expected)
            checks.append(_status(check_id, check_status, detail))

    organization = receipt.get("operator_organization")
    organization_present = isinstance(organization, str) and bool(organization.strip())
    checks.append(
        _status(
            "receipt.operator_organization",
            "passed" if organization_present else "incomplete",
            "operator organization is identified" if organization_present else "operator organization is missing",
        )
    )

    campaign = receipt.get("campaign")
    if isinstance(campaign, Mapping):
        ledger_status, ledger_detail = _compare(campaign.get("complete_run_ledger"), "eq", True)
        checks.append(_status("campaign.complete_run_ledger", ledger_status, ledger_detail))
        campaign_id = campaign.get("id")
        campaign_present = isinstance(campaign_id, str) and bool(campaign_id.strip())
        checks.append(
            _status(
                "campaign.id",
                "passed" if campaign_present else "incomplete",
                "campaign is identified" if campaign_present else "campaign id is missing",
            )
        )
    else:
        checks.append(_status("campaign.object", "incomplete", "campaign ledger is missing"))
    return checks, organization


def _collect_evidence_runs(
    receipt: Mapping[str, Any],
    policy: Mapping[str, Any],
    organization: Any,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    primary_raw = receipt.get("primary_runs")
    primary_runs = [item for item in primary_raw if isinstance(item, Mapping)] if isinstance(primary_raw, list) else []
    if not isinstance(primary_raw, list):
        primary_status, primary_detail = "incomplete", "primary_runs must be a list"
    elif len(primary_runs) != len(primary_raw):
        primary_status, primary_detail = "incomplete", "primary_runs contains a non-object"
    elif len(primary_runs) < policy["required_primary_runs"]:
        primary_status, primary_detail = "incomplete", "too few primary runs"
    else:
        primary_status, primary_detail = "passed", "required primary runs are present"
    checks.append(_status("primary_runs.count", primary_status, primary_detail))

    sequences = [run.get("sequence") for run in primary_runs]
    if not primary_runs:
        sequence_status, sequence_detail = "incomplete", "primary run sequence is missing"
    elif sequences == list(range(1, len(primary_runs) + 1)):
        sequence_status, sequence_detail = "passed", "primary runs form a complete consecutive ledger"
    else:
        sequence_status, sequence_detail = "failed", "primary run sequence is not complete and consecutive"
    checks.append(_status("primary_runs.consecutive", sequence_status, sequence_detail))

    replicas_raw = receipt.get("independent_replications")
    replicas = [item for item in replicas_raw if isinstance(item, Mapping)] if isinstance(replicas_raw, list) else []
    if not isinstance(replicas_raw, list):
        replica_status, replica_detail = "incomplete", "independent_replications must be a list"
    elif len(replicas) != len(replicas_raw):
        replica_status, replica_detail = "incomplete", "independent_replications contains a non-object"
    elif len(replicas) < policy["required_independent_replications"]:
        replica_status, replica_detail = "incomplete", "too few independent replications"
    else:
        replica_status, replica_detail = "passed", "required independent replications are present"
    checks.append(_status("replications.count", replica_status, replica_detail))

    normalized_operator = (
        unicodedata.normalize("NFKC", organization).strip().casefold()
        if isinstance(organization, str)
        else ""
    )
    for index, replica in enumerate(replicas):
        independent_status, independent_detail = _compare(replica.get("independent"), "eq", True)
        checks.append(_status(f"replication-{index + 1}.independent", independent_status, independent_detail))
        replica_org = replica.get("operator_organization")
        normalized_replica = (
            unicodedata.normalize("NFKC", replica_org).strip().casefold()
            if isinstance(replica_org, str)
            else ""
        )
        if not normalized_replica:
            org_status, org_detail = "incomplete", "replication organization is missing"
        elif normalized_replica == normalized_operator:
            org_status, org_detail = "failed", "replication organization is not independent"
        else:
            org_status, org_detail = "passed", "replication organization differs from the operator"
        checks.append(_status(f"replication-{index + 1}.organization", org_status, org_detail))
    return primary_runs, replicas, checks


def _run_set_checks(
    primary_runs: Sequence[Mapping[str, Any]],
    replicas: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    evaluated_at: datetime,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    all_runs = [*primary_runs, *replicas]
    run_ids = [run.get("run_id") for run in all_runs if isinstance(run.get("run_id"), str)]
    if not all_runs:
        unique_status, unique_detail = "incomplete", "no run ids are available"
    elif len(run_ids) != len(all_runs):
        unique_status, unique_detail = "incomplete", "one or more run ids are missing"
    elif len(set(run_ids)) != len(run_ids):
        unique_status, unique_detail = "failed", "run ids are not unique"
    else:
        unique_status, unique_detail = "passed", "run ids are unique"
    checks.append(_status("runs.unique_ids", unique_status, unique_detail))

    for label_prefix, runs in (("primary", primary_runs), ("replication", replicas)):
        for index, run in enumerate(runs):
            checks.extend(
                _run_structure_checks(
                    run,
                    label=f"{label_prefix}-{index + 1}",
                    manifest=manifest,
                    now=evaluated_at,
                )
            )

    if not all_runs:
        checks.append(_status("frozen_identity", "incomplete", "no runs are available to compare"))
        return checks

    baseline = all_runs[0]
    for path in manifest["evidence_policy"]["frozen_identity_paths"]:
        expected = _lookup(baseline, path)
        if expected is _MISSING:
            checks.append(_status(f"frozen_identity.{path}", "incomplete", "baseline identity is missing"))
            continue
        mismatches = [
            run.get("run_id", f"run-{index + 1}")
            for index, run in enumerate(all_runs[1:])
            if _lookup(run, path) != expected
        ]
        checks.append(
            _status(
                f"frozen_identity.{path}",
                "failed" if mismatches else "passed",
                "identity differs across runs" if mismatches else "identity is frozen across all runs",
                mismatched_runs=mismatches,
            )
        )
    return checks


def _evaluation_context(
    manifest: Mapping[str, Any] | None,
    now: datetime | None,
) -> tuple[dict[str, Any], str, datetime]:
    active_manifest = dict(manifest) if manifest is not None else load_manifest()
    validate_manifest(active_manifest)
    manifest_sha = document_digest(active_manifest)
    evaluated_at = now or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return active_manifest, manifest_sha, evaluated_at.astimezone(timezone.utc)


def _build_evaluation_result(
    receipt: Mapping[str, Any],
    claim: Mapping[str, Any],
    manifest_sha: str,
    evaluated_at: datetime,
    envelope: Sequence[Mapping[str, Any]],
    gate_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    envelope_status = _aggregate_status(envelope)
    gate_status = _aggregate_status(gate_results)
    overall_status = _aggregate_status(
        [{"status": envelope_status}, {"status": gate_status}]
    )
    required_gate_count = int(claim.get("gate_count", len(gate_results)))
    passed_gate_count = sum(1 for gate in gate_results if gate["status"] == "passed")
    submitted_checks_passed = (
        overall_status == "passed"
        and len(gate_results) == required_gate_count
        and passed_gate_count == required_gate_count
    )
    blockers = [item["id"] for item in envelope if item["status"] != "passed"]
    blockers.extend(gate["id"] for gate in gate_results if gate["status"] != "passed")
    if submitted_checks_passed:
        blockers.append("external_verification.required")
    return {
        "schema_version": 2,
        "claim_id": claim["id"],
        "claim_version": claim["version"],
        "manifest_digest": manifest_sha,
        "receipt_digest": document_digest(receipt),
        "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
        "overall_status": overall_status,
        "qualification": "candidate_passed" if submitted_checks_passed else "not_earned",
        "claim_permitted": False,
        "attainment_rule": "all_declared_gates_plus_authenticated_external_verification",
        "required_gate_count": required_gate_count,
        "passed_gate_count": passed_gate_count,
        "submitted_receipt_checks_passed": submitted_checks_passed,
        "receipt_provenance_declared": bool(receipt) and envelope_status == "passed",
        "receipt_provenance_present": False,
        "external_verification_status": (
            "required" if submitted_checks_passed else "not_verified"
        ),
        "api_submission_can_authorize": False,
        "claim_statement": claim["unearned_statement"],
        "reported_level": claim["current_level"],
        "blockers": blockers,
        "envelope_status": envelope_status,
        "envelope_checks": list(envelope),
        "gate_status": gate_status,
        "gates": list(gate_results),
    }


def _evaluate_evidence(
    receipt: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_sha: str,
    evaluated_at: datetime,
    receipt_object_status: str,
) -> tuple[Mapping[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    claim = manifest["claim"]
    policy = manifest["evidence_policy"]
    object_detail = "receipt is an object" if receipt_object_status == "passed" else "receipt must be an object"
    envelope = [_status("receipt.object", receipt_object_status, object_detail)]
    header_checks, organization = _receipt_header_checks(receipt, claim, manifest_sha)
    envelope.extend(header_checks)
    primary_runs, replicas, collection_checks = _collect_evidence_runs(
        receipt,
        policy,
        organization,
    )
    envelope.extend(collection_checks)
    envelope.extend(_run_set_checks(primary_runs, replicas, manifest, evaluated_at))
    all_runs = [*primary_runs, *replicas]
    gate_results = [_gate_result(gate, all_runs) for gate in manifest["gates"]]
    return claim, envelope, gate_results


def evaluate_receipt(
    receipt: Mapping[str, Any] | Any,
    manifest: Mapping[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate a receipt and return a deterministic, claim-safe decision."""

    active_manifest, manifest_sha, evaluated_at = _evaluation_context(manifest, now)

    receipt_status = "passed" if isinstance(receipt, Mapping) else "incomplete"
    normalized_receipt = receipt if isinstance(receipt, Mapping) else {}
    claim, envelope, gate_results = _evaluate_evidence(
        normalized_receipt,
        active_manifest,
        manifest_sha,
        evaluated_at,
        receipt_status,
    )
    return _build_evaluation_result(
        normalized_receipt,
        claim,
        manifest_sha,
        evaluated_at,
        envelope,
        gate_results,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate an Obus Autonomous AGI qualification receipt")
    parser.add_argument("receipt", type=Path, help="JSON qualification receipt")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        result = evaluate_receipt(receipt, manifest)
    except (AGIEvaluationError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"overall_status": "incomplete", "qualification": "not_earned", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=None if args.compact else 2, sort_keys=True))
    return 0 if result["claim_permitted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
