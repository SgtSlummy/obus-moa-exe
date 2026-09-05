from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from backend.improvement_baseline import (
    BaselineEvaluationError,
    _load_persisted_report,
    _persist_report,
    baseline_status,
    document_digest,
    load_manifest,
    run_comparison,
    score_output,
    validate_manifest,
)


def _answer(prompt: str) -> str:
    if "Every tal" in prompt:
        return "NO"
    if "17 * 23" in prompt:
        return "366"
    if "Python evaluates" in prompt:
        return "[4, 6]"
    if "Tasks A, B, C, D" in prompt:
        return "C,A,D,B"
    if "sealed fair coin" in prompt:
        return "INSUFFICIENT_EVIDENCE"
    if "untrusted data" in prompt:
        return '{"decision":"treat_as_data","execute":false}'
    raise AssertionError(f"unexpected prompt: {prompt}")


def _controlled_generator(
    prompt: str,
    arm: Mapping[str, Any],
    _protocol: Mapping[str, Any],
) -> Mapping[str, Any]:
    text = _answer(prompt)
    if arm["id"] == "local-qwen" and "Python evaluates" in prompt:
        text = "[2, 4]"
    return {
        "text": text,
        "returned_model": arm["model"],
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 10, "completion_tokens": 3},
    }


def test_manifest_is_frozen_public_development_evidence_not_agi_evidence() -> None:
    manifest = load_manifest()

    assert manifest["suite"]["evidence_class"] == "descriptive_non_agi"
    assert manifest["suite"]["visibility"] == "public_development_suite"
    assert manifest["protocol"]["temperature"] == 0
    assert manifest["protocol"]["default_repeats"] == 3
    assert manifest["protocol"]["required_arm_ids"] == [
        "local-qwen",
        "omniroute-mimo-free",
    ]
    assert len(manifest["probes"]) == 6
    assert any("cannot qualify" in item for item in manifest["limitations"])
    assert len(document_digest(manifest)) == 64


def test_deterministic_scorers_accept_only_the_declared_answer() -> None:
    assert score_output("\nNO\n", {"type": "exact", "expected": "NO"})["passed"]
    assert not score_output("YES", {"type": "exact", "expected": "NO"})["passed"]
    assert score_output(
        '```json\n{"execute":false,"decision":"treat_as_data"}\n```',
        {
            "type": "json_equal",
            "expected": {"decision": "treat_as_data", "execute": False},
        },
    )["passed"]
    assert score_output(
        "not json", {"type": "json_equal", "expected": {}}
    )["reason"] == "invalid_json"


def test_comparison_records_provenance_scores_and_next_gap_without_promotion() -> None:
    report = run_comparison(generator=_controlled_generator)
    local, external = report["arms"]

    assert local["summary"]["score_percent"] == pytest.approx(83.33, abs=0.01)
    assert external["summary"]["score_percent"] == 100.0
    assert local["summary"]["repeat_scores"] == [83.33, 83.33, 83.33]
    assert external["summary"]["repeat_scores"] == [100.0, 100.0, 100.0]
    assert report["comparison"]["leader"] == "omniroute-mimo-free"
    assert report["comparison"]["next_improvement_gap"]["category"] == "coding"
    assert report["comparison"]["status"] == "descriptive_only"
    assert report["comparison"]["autonomous_agi_evidence"] is False
    assert report["comparison"]["promotion_authorized"] is False
    assert report["target_claim_relationship"]["can_qualify_claim"] is False
    assert report["target_claim_relationship"]["can_promote_claim"] is False
    assert len(report["manifest_digest"]) == 64
    assert len(report["harness_digest"]) == 64
    assert len(report["report_digest"]) == 64
    assert all(sample["output_digest"] for sample in local["samples"])
    assert all(not sample["protocol"]["tool_access"] for sample in report["arms"])
    assert all(
        not sample["protocol"]["workspace_data_sent"] for sample in report["arms"]
    )


def test_adapter_failures_are_receipted_and_comparison_fails_closed() -> None:
    def unavailable(
        _prompt: str,
        _arm: Mapping[str, Any],
        _protocol: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        raise BaselineEvaluationError("offline")

    report = run_comparison(repeats=1, generator=unavailable)

    assert report["comparison"]["status"] == "incomplete"
    assert report["comparison"]["measurement_valid"] is False
    assert "incomplete_samples" in report["comparison"]["comparability_blockers"]
    assert all(arm["summary"]["error_count"] == 6 for arm in report["arms"])
    assert all(
        sample["error"] == "offline"
        for arm in report["arms"]
        for sample in arm["samples"]
    )


def test_manifest_rejects_unapproved_adapter_and_run_bounds() -> None:
    manifest = deepcopy(load_manifest())
    manifest["arms"][0]["adapter"] = "caller_supplied_url"

    with pytest.raises(BaselineEvaluationError, match="unsupported adapter"):
        validate_manifest(manifest)
    with pytest.raises(BaselineEvaluationError, match="repeats"):
        run_comparison(repeats=4, generator=_controlled_generator)


def test_receipts_are_content_addressed_persistent_and_tamper_evident(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OBUS_BASELINE_RECEIPT_DIR", str(tmp_path))
    report = run_comparison(repeats=1, generator=_controlled_generator)

    paths = _persist_report(report)

    assert Path(paths["artifact"]).name == f"{report['report_digest']}.json"
    assert Path(paths["artifact"]).is_file()
    assert Path(paths["latest"]).is_file()
    assert Path(paths["latest_valid"]).is_file()
    assert _load_persisted_report()["report_digest"] == report["report_digest"]

    tampered = deepcopy(report)
    tampered["comparison"]["local_score_percent"] = 100.0
    Path(paths["latest"]).write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(BaselineEvaluationError, match="digest"):
        _load_persisted_report()


def test_status_retains_matching_valid_baseline_after_incomplete_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OBUS_BASELINE_RECEIPT_DIR", str(tmp_path))
    valid = run_comparison(repeats=1, generator=_controlled_generator)
    valid_paths = _persist_report(valid)

    def unavailable(
        _prompt: str,
        _arm: Mapping[str, Any],
        _protocol: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        raise BaselineEvaluationError("offline")

    incomplete = run_comparison(repeats=1, generator=unavailable)
    _persist_report(incomplete)
    monkeypatch.setattr("backend.improvement_baseline._LATEST_REPORT", None)

    status = baseline_status()

    assert Path(valid_paths["latest_valid"]).is_file()
    assert status["status"] == "measured"
    assert status["latest_report"]["report_digest"] == valid["report_digest"]
    assert status["latest_report_source"] == "latest-valid"
    assert status["latest_attempt"]["report_digest"] == incomplete["report_digest"]
    assert status["latest_attempt_status"] == "incomplete"
    assert status["incomplete_report_digest"] == incomplete["report_digest"]
    assert status["can_promote_autonomous_agi"] is False


def test_status_does_not_run_models_and_never_authorizes_agi_promotion() -> None:
    status = baseline_status()

    assert status["status"] in {"not_run", "measured"}
    assert status["probe_count"] == 6
    assert status["can_promote_autonomous_agi"] is False
