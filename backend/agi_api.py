"""Read-only Autonomous AGI claim and guarded-improvement API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .agi_evaluation import (
    AGIEvaluationError,
    evaluate_receipt,
    load_manifest,
)
from .epistemic_policy import epistemic_policy_status_payload
from .improvement_baseline import (
    BaselineEvaluationError,
    baseline_status,
    run_and_record_comparison,
)
from .improvement_evaluation import (
    ImprovementEvaluationError,
    evaluate_improvement_receipt,
    load_policy,
)
from .improvement_evaluation import (
    document_digest as improvement_policy_digest,
)

router = APIRouter(prefix="/api/agi", tags=["Autonomous AGI"])


def _load_claim_status() -> dict[str, Any]:
    try:
        manifest = load_manifest()
        attainment = evaluate_receipt({})
        improvement_policy = load_policy()
    except (AGIEvaluationError, ImprovementEvaluationError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Autonomous AGI evidence policy is unavailable",
        ) from exc

    try:
        measured_baseline = baseline_status()
    except BaselineEvaluationError:
        measured_baseline = {
            "schema_version": 1,
            "status": "unavailable",
            "latest_report": None,
            "can_promote_autonomous_agi": False,
        }

    claim = manifest["claim"]
    gates = attainment["gates"]
    gate_counts = {
        status: sum(1 for gate in gates if gate["status"] == status)
        for status in ("passed", "failed", "incomplete")
    }
    policy_metadata = improvement_policy["policy"]
    authority = improvement_policy["authority"]
    requirements = improvement_policy["promotion_requirements"]

    return {
        "schema_version": 2,
        "target_claim": {
            "label": "A23-verified Autonomous AGI",
            "id": claim["id"],
            "version": claim["version"],
            "definition": claim["definition"],
            "current_level": attainment["reported_level"],
            "target_level": claim["target_level"],
            "gate_count": claim["gate_count"],
            "attainment_rule": attainment["attainment_rule"],
            "claim_permitted": attainment["claim_permitted"],
            "claim_statement": attainment["claim_statement"],
            "interpretation": claim["interpretation"],
            "ladder": manifest["claim_ladder"],
        },
        "evidence": {
            "overall_status": attainment["overall_status"],
            "qualification": attainment["qualification"],
            "manifest_digest": attainment["manifest_digest"],
            "required_gate_count": attainment["required_gate_count"],
            "passed_gate_count": attainment["passed_gate_count"],
            "reported_level": attainment["reported_level"],
            "submitted_receipt_checks_passed": attainment[
                "submitted_receipt_checks_passed"
            ],
            "receipt_provenance_declared": attainment[
                "receipt_provenance_declared"
            ],
            "receipt_provenance_present": attainment["receipt_provenance_present"],
            "external_verification_status": attainment[
                "external_verification_status"
            ],
            "api_submission_can_authorize": attainment[
                "api_submission_can_authorize"
            ],
            "gate_counts": gate_counts,
            "gates": gates,
            "blockers": attainment["blockers"],
            "required_primary_runs": manifest["evidence_policy"][
                "required_primary_runs"
            ],
            "required_independent_replications": manifest["evidence_policy"][
                "required_independent_replications"
            ],
            "minimum_independent_organizations": manifest["evidence_policy"][
                "minimum_independent_organizations"
            ],
            "self_certification_permitted": manifest["evidence_policy"][
                "self_certification_permitted"
            ],
            "receipt_state": (
                "No qualification receipt is persisted in this read-only status view. "
                "API-submitted receipts are screening-only and cannot authorize A23."
            ),
        },
        "guarded_improvement": {
            "id": policy_metadata["id"],
            "version": policy_metadata["version"],
            "policy_digest": improvement_policy_digest(improvement_policy),
            "statement": policy_metadata["statement"],
            "purpose": policy_metadata["purpose"],
            "lifecycle": improvement_policy["lifecycle"],
            "autonomous_actions": authority["autonomous_actions"],
            "human_only_actions": authority["human_only_actions"],
            "minimum_candidate_delta": requirements["minimum_candidate_delta"],
            "minimum_reproducible_runs": requirements[
                "minimum_reproducible_runs"
            ],
        },
        "measured_baseline": measured_baseline,
        "separation_of_concerns": {
            "runtime_ready_is_capability_verified": False,
            "self_evaluation_is_independent_verification": False,
            "submitted_receipt_checks_are_verified_provenance": False,
            "evaluation_endpoint_mutates_runtime": False,
            "evaluation_endpoint_promotes_candidates": False,
            "evaluation_endpoint_can_authorize_a23": False,
            "synthetic_baseline_is_agi_evidence": False,
            "baseline_endpoint_promotes_candidates": False,
        },
    }


@router.get("/status")
def autonomous_agi_status() -> dict[str, Any]:
    """Return the defined target claim and its current fail-closed evidence state."""

    return _load_claim_status()


@router.get("/campaign-envelope")
def autonomous_agi_campaign_envelope() -> dict[str, Any]:
    """Return a read-only external-verifier handoff, never a qualification receipt."""

    from .a23_campaign import build_campaign_envelope

    return build_campaign_envelope(_load_claim_status())


@router.post("/evaluate")
def evaluate_autonomous_agi(receipt: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a caller-supplied claim receipt without storing or acting on it."""

    try:
        from hashlib import sha256
        import json

        evaluation = evaluate_receipt(receipt)
        canonical_receipt = json.dumps(
            receipt,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return {
            **evaluation,
            "receipt_digest": sha256(canonical_receipt).hexdigest(),
            "evaluation_disposition": {
                "stored": False,
                "promotes_claim": False,
                "requires_independent_replication": True,
            },
        }
    except AGIEvaluationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/baseline/status")
def measured_improvement_baseline_status() -> dict[str, Any]:
    """Return the frozen suite identity and latest in-process measurement."""

    try:
        return baseline_status()
    except BaselineEvaluationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Measured improvement baseline is unavailable",
        ) from exc


@router.post("/baseline/run")
def run_measured_improvement_baseline(
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run only the frozen public probes; never execute tools or promote a claim."""

    body = request or {}
    unknown = set(body) - {"repeats"}
    if unknown:
        raise HTTPException(status_code=422, detail="Only repeats may be specified")
    try:
        return run_and_record_comparison(repeats=body.get("repeats"))
    except BaselineEvaluationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/epistemic/policy")
def epistemic_policy_status() -> dict[str, object]:
    return epistemic_policy_status_payload()


@router.get("/improvement/policy")
def guarded_improvement_policy() -> dict[str, Any]:
    """Return the complete versioned policy used for improvement receipts."""

    try:
        policy = load_policy()
    except ImprovementEvaluationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Guarded improvement policy is unavailable",
        ) from exc
    return {"policy": policy, "policy_digest": improvement_policy_digest(policy)}


@router.post("/improvement/evaluate")
def evaluate_guarded_improvement(receipt: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an improvement receipt; this endpoint never promotes a candidate."""

    try:
        return evaluate_improvement_receipt(receipt)
    except ImprovementEvaluationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
