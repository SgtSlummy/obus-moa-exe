from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from backend.agi_api import (
    autonomous_agi_status,
    evaluate_guarded_improvement,
    measured_improvement_baseline_status,
    router,
)

ROOT = Path(__file__).resolve().parents[1]


def test_status_defines_autonomous_agi_as_target_and_reports_attainment_separately() -> None:
    payload = autonomous_agi_status()
    claim = payload["target_claim"]
    evidence = payload["evidence"]

    assert payload["schema_version"] == 2
    assert claim["label"] == "A23-verified Autonomous AGI"
    assert claim["version"] == "2.0.0"
    assert claim["definition"].startswith("An Autonomous AGI is an engineered system")
    assert claim["current_level"] == "A2"
    assert claim["target_level"] == "A23"
    assert claim["gate_count"] == 23
    assert (
        claim["attainment_rule"]
        == "all_declared_gates_plus_authenticated_external_verification"
    )
    assert claim["claim_permitted"] is False
    assert evidence["qualification"] == "not_earned"
    assert evidence["required_gate_count"] == 23
    assert evidence["passed_gate_count"] == 0
    assert evidence["gate_counts"] == {"passed": 0, "failed": 0, "incomplete": 23}
    assert evidence["reported_level"] == "A2"
    assert evidence["submitted_receipt_checks_passed"] is False
    assert evidence["receipt_provenance_declared"] is False
    assert evidence["receipt_provenance_present"] is False
    assert evidence["external_verification_status"] == "not_verified"
    assert evidence["api_submission_can_authorize"] is False
    assert evidence["required_primary_runs"] == 3
    assert evidence["required_independent_replications"] == 1
    assert evidence["minimum_independent_organizations"] == 1
    assert evidence["self_certification_permitted"] is False
    assert payload["measured_baseline"]["can_promote_autonomous_agi"] is False
    assert payload["separation_of_concerns"] == {
        "runtime_ready_is_capability_verified": False,
        "self_evaluation_is_independent_verification": False,
        "submitted_receipt_checks_are_verified_provenance": False,
        "evaluation_endpoint_mutates_runtime": False,
        "evaluation_endpoint_promotes_candidates": False,
        "evaluation_endpoint_can_authorize_a23": False,
        "synthetic_baseline_is_agi_evidence": False,
        "baseline_endpoint_promotes_candidates": False,
    }


def test_guarded_improvement_endpoint_fails_closed_without_evidence() -> None:
    result = evaluate_guarded_improvement({})

    assert result["overall_status"] == "incomplete"
    assert result["promotion_authorized"] is False
    assert result["autonomous_promotion_permitted"] is False


def test_measured_baseline_status_is_read_only_and_non_promotional() -> None:
    result = measured_improvement_baseline_status()

    assert result["suite"]["evidence_class"] == "descriptive_non_agi"
    assert result["probe_count"] == 6
    assert result["can_promote_autonomous_agi"] is False


def test_router_exposes_read_only_status_and_separate_evaluators() -> None:
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]

    assert "get" in paths["/api/agi/status"]
    assert "post" in paths["/api/agi/evaluate"]
    assert "get" in paths["/api/agi/baseline/status"]
    assert "post" in paths["/api/agi/baseline/run"]
    assert "get" in paths["/api/agi/improvement/policy"]
    assert "post" in paths["/api/agi/improvement/evaluate"]


def test_main_registers_the_narrow_agi_router() -> None:
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    assert "from .agi_api import router as agi_router" in source
    assert source.count("app.include_router(agi_router)") == 1


def test_settings_surface_loads_claim_without_unsafe_html_rendering() -> None:
    index = (ROOT / "backend" / "static" / "index.html").read_text(encoding="utf-8")
    script = (
        ROOT / "backend" / "static" / "aui" / "agi-claim.js"
    ).read_text(encoding="utf-8")

    assert index.count('id="agi-claim-card"') == 1
    assert index.count('id="agi-improvement-card"') == 1
    assert index.count('id="agi-baseline-card"') == 1
    assert index.count('id="agi-baseline-run"') == 1
    assert index.count('id="agi-claim-verified"') == 1
    assert index.count('id="agi-claim-target"') == 1
    assert index.count('id="agi-claim-attainment"') == 1
    assert index.count('/static/aui/agi-claim.js?v=agi-claim-historical-evidence-1') == 1
    assert 'fetch("/api/agi/status"' in script
    assert 'fetch("/api/agi/baseline/run"' in script
    assert "textContent" in script
    assert "innerHTML" not in script
    assert "Status unavailable — claim not permitted" in script
    assert 'targetLevel === "A23"' in script
    assert "gates.length === 23" in script
    assert "receipt_provenance_present === true" in script
    assert "currentLevel !== targetLevel" in script
    assert "currentLevel === reportedLevel" in script
    assert "API receipts are screening-only" in script
    assert '|| "A4"' not in script
    assert "Runtime warmth or model availability never substitutes" in script
    assert "this public suite cannot earn or promote" in index
