from __future__ import annotations

from copy import deepcopy

import pytest

from backend.improvement_evaluation import (
    ImprovementEvaluationError,
    document_digest,
    evaluate_improvement_receipt,
    load_policy,
    validate_policy,
)


def _valid_receipt() -> dict:
    policy = load_policy()
    proposal_id = "proposal-001"
    return {
        "schema_version": 1,
        "policy_id": policy["policy"]["id"],
        "policy_version": policy["policy"]["version"],
        "policy_digest": document_digest(policy),
        "candidate": {
            "proposal_id": proposal_id,
            "objective": "Improve deterministic route selection without safety regressions.",
            "proposer_id": "candidate-agent",
            "baseline_digest": "a" * 64,
            "candidate_digest": "b" * 64,
            "diff_digest": "c" * 64,
            "source_tree_digest": "d" * 64,
            "self_promotion_requested": False,
        },
        "isolation": {
            "sandboxed": True,
            "network_default_deny": True,
            "bounded_resources": True,
        },
        "evaluator": {
            "evaluator_digest": "e" * 64,
            "public_suite_digest": "f" * 64,
            "heldout_suite_digest": "1" * 64,
            "frozen_before_proposal": True,
            "candidate_modified_evaluator": False,
            "candidate_accessed_heldout": False,
            "independent_verifier_id": "independent-verifier",
        },
        "results": {
            "baseline_score": 0.50,
            "candidate_score": 0.52,
            "public_suite_passed": True,
            "heldout_suite_passed": True,
            "regression_suite_passed": True,
            "safety_suite_passed": True,
            "contract_suite_passed": True,
            "reproducible_runs": 3,
        },
        "governance": {
            "policy_boundary_changed": False,
            "critical_incidents": 0,
            "human_authorization": {
                "approval_id": "approval-001",
                "approval_digest": "2" * 64,
                "approver_id": "operator-hermes",
                "approver_kind": "human",
                "independent_from_candidate": True,
                "action": "authorize-promotion",
                "scope": f"promote:{proposal_id}",
            },
        },
        "rollback": {
            "checkpoint_id": "checkpoint-001",
            "checkpoint_digest": "3" * 64,
            "restore_tested": True,
        },
        "monitoring": {
            "canary_required": True,
            "rollback_trigger_defined": True,
            "post_promotion_checks_defined": True,
        },
    }


def test_empty_receipt_fails_closed_as_incomplete() -> None:
    result = evaluate_improvement_receipt({})

    assert result["overall_status"] == "incomplete"
    assert result["decision"] == "incomplete"
    assert result["promotion_authorized"] is False
    assert result["autonomous_promotion_permitted"] is False
    assert "governance.human_authorization.approval_id" in result["blockers"]


def test_complete_receipt_can_be_authorized_but_never_self_promotes() -> None:
    result = evaluate_improvement_receipt(_valid_receipt())

    assert result["overall_status"] == "passed"
    assert result["decision"] == "authorized-for-promotion"
    assert result["promotion_authorized"] is True
    assert result["autonomous_promotion_permitted"] is False
    assert result["blockers"] == []


@pytest.mark.parametrize(
    ("path", "value", "blocker"),
    [
        (
            ("evaluator", "candidate_modified_evaluator"),
            True,
            "evaluator.candidate_modified_evaluator",
        ),
        (
            ("evaluator", "candidate_accessed_heldout"),
            True,
            "evaluator.candidate_accessed_heldout",
        ),
        (
            ("results", "safety_suite_passed"),
            False,
            "results.safety_suite_passed",
        ),
        (
            ("governance", "policy_boundary_changed"),
            True,
            "governance.policy_boundary_changed",
        ),
        (
            ("rollback", "restore_tested"),
            False,
            "rollback.restore_tested",
        ),
    ],
)
def test_unsafe_or_unverifiable_changes_are_rejected(
    path: tuple[str, str], value: object, blocker: str
) -> None:
    receipt = _valid_receipt()
    receipt[path[0]][path[1]] = value

    result = evaluate_improvement_receipt(receipt)

    assert result["overall_status"] == "failed"
    assert result["decision"] == "reject"
    assert result["promotion_authorized"] is False
    assert blocker in result["blockers"]


def test_candidate_cannot_be_its_own_verifier_or_human_approver() -> None:
    receipt = _valid_receipt()
    receipt["evaluator"]["independent_verifier_id"] = "candidate-agent"
    receipt["governance"]["human_authorization"]["approver_kind"] = "agent"

    result = evaluate_improvement_receipt(receipt)

    assert result["overall_status"] == "failed"
    assert "evaluator.independent_verifier" in result["blockers"]
    assert "governance.human_authorization.approver_kind" in result["blockers"]


def test_missing_human_authorization_remains_incomplete() -> None:
    receipt = _valid_receipt()
    del receipt["governance"]["human_authorization"]

    result = evaluate_improvement_receipt(receipt)

    assert result["overall_status"] == "incomplete"
    assert result["promotion_authorized"] is False


def test_policy_digest_mismatch_rejects_candidate() -> None:
    receipt = _valid_receipt()
    receipt["policy_digest"] = "0" * 64

    result = evaluate_improvement_receipt(receipt)

    assert result["overall_status"] == "failed"
    assert "policy_digest" in result["blockers"]


def test_policy_cannot_delegate_promotion_authority_to_an_agent() -> None:
    policy = deepcopy(load_policy())
    policy["authority"]["human_only_actions"].remove("authorize-promotion")

    with pytest.raises(ImprovementEvaluationError):
        validate_policy(policy)
