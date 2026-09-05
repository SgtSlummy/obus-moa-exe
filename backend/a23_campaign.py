"""Build deterministic, non-authoritative A23 evaluator campaign envelopes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_PUBLIC_ARTIFACTS = (
    "AUTONOMOUS_AGI_CLAIM.md",
    "data/autonomous-agi-evaluation-manifest.json",
    "backend/agi_evaluation.py",
    "data/autonomous-improvement-policy.json",
)


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_digest(relative_path: str) -> dict[str, str]:
    path = _REPOSITORY_ROOT / relative_path
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _source_identity() -> dict[str, object]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "commit": None}
    revision = completed.stdout.strip()
    if completed.returncode != 0 or len(revision) != 40:
        return {"status": "unavailable", "commit": None}
    return {"status": "tracked", "commit": revision}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def build_campaign_envelope(claim_status: Mapping[str, Any]) -> dict[str, object]:
    """Return a portable A23 campaign plan without creating qualification evidence.

    The envelope deliberately contains no held-out data, evaluator secrets, task
    answers, operator identity, receipt, or promotion mechanism.  Its digest is
    stable for identical claim status and frozen public artifacts.
    """

    target = _mapping(claim_status.get("target_claim"))
    evidence = _mapping(claim_status.get("evidence"))
    gates = evidence.get("gates")
    gate_ids = [
        item["id"]
        for item in gates
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    ] if isinstance(gates, list) else []
    required_primary_runs = evidence.get("required_primary_runs")
    required_replications = evidence.get("required_independent_replications")

    envelope: dict[str, object] = {
        "schema_version": 1,
        "kind": "obus-a23-external-evaluation-campaign-envelope",
        "claim": {
            "id": target.get("id"),
            "version": target.get("version"),
            "target_level": target.get("target_level"),
            "manifest_digest": evidence.get("manifest_digest"),
        },
        "current_status": {
            "reported_level": evidence.get("reported_level"),
            "qualification": evidence.get("qualification"),
            "passed_gate_count": evidence.get("passed_gate_count"),
            "required_gate_count": evidence.get("required_gate_count"),
        },
        "frozen_identity": {
            "source_revision": _source_identity(),
            "public_artifacts": [_file_digest(path) for path in _PUBLIC_ARTIFACTS],
        },
        "evidence_requirements": {
            "primary_runs": {
                "minimum": required_primary_runs,
                "must_be_consecutive": True,
                "must_have_unique_ids": True,
            },
            "independent_replications": {
                "minimum": required_replications,
                "requires_different_organization": True,
                "operator_organization_must_be_declared": True,
            },
            "required_gate_ids": gate_ids,
            "retain_failed_incomplete_and_rejected_records": True,
        },
        "evaluator_custody": {
            "held_out_data_included": False,
            "operator_may_access_held_out_answers": False,
            "evaluator_must_control_scoring": True,
            "receipt_is_included": False,
        },
        "evaluation_protocol": {
            "purpose": "execution and reporting requirements, not qualification evidence",
            "objective_must_be_declared_before_runs": True,
            "development_and_sealed_test_must_be_separate": True,
            "human_expert_duration_baselines_required_for_time_horizon_claims": True,
            "per_run_provenance_required": [
                "runtime_model_policy_and_scaffold_configuration",
                "tool_and_resource_budgets",
                "task_identity_and_outcome",
            ],
            "per_task_reliability_and_uncertainty_reporting_required": True,
            "test_time_compute_budget_curve_required_when_claims_are_budget_sensitive": True,
            "minimum_informative_budget_or_diminishing_returns_review_required": True,
            "environment_solvability_and_infrastructure_failures_must_be_reviewed": True,
            "human_adjudication_required_for_ambiguous_or_judge_disagreement": True,
            "scoring_criteria_and_judge_prompts_must_be_stress_tested": True,
            "reward_hack_review_required": True,
            "failures_retries_and_incomplete_runs_must_be_reported": True,
            "reference_frameworks": [
                "METR time-horizon methodology (alignment only; evaluator chooses the benchmark)",
                "NIST AI 800-2 automated benchmark practices (alignment only)",
                "UK AISI agentic-testing and sandboxing practices (alignment only; evaluator chooses methods)",
            ],
        },
        "authority_boundary": {
            "campaign_envelope_is_qualification_receipt": False,
            "can_submit_receipt": False,
            "can_promote_autonomous_agi": False,
            "qualification_requires_authenticated_external_decision": True,
        },
        "operator_actions": [
            "appoint an evaluator independent from the primary operator",
            "freeze the full runtime, model, policy, and evaluator configuration",
            "run the required sealed primary sequence",
            "obtain an independently operated organizational replication",
            "evaluate a complete receipt with the official fail-closed evaluator",
        ],
    }
    envelope["envelope_digest"] = _canonical_digest(envelope)
    return envelope
