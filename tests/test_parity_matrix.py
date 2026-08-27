from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.parity_matrix import (
    MatrixValidationError,
    blank_receipt,
    compare_receipts,
    format_markdown,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "obus-codex-comparison-manifest.json"
SCRIPT_PATH = ROOT / "scripts" / "obus_codex_comparison.py"


def load_manifest() -> dict:
    return validate_manifest(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def completed_receipt(product: str, manifest: dict, *, p95_seconds: float = 1.0) -> dict:
    receipt = blank_receipt(
        product,
        manifest,
        run={
            "id": f"{product}-run-1",
            "started_at": "2026-08-26T00:00:00Z",
            "worktree_sha": "abc123",
            "model": "comparison-model",
            "product_version": "test-version",
        },
        environment={
            "os": "Windows test",
            "hardware": "test hardware",
            "sandbox": "workspace-write",
            "approval_policy": "on-request",
            "network": "disabled",
        },
    )
    for row in receipt["fixtures"]:
        row.update({"status": "passed", "score": 5, "evidence": [f"artifacts/{product}/{row['id']}.json"]})
        if row["id"] == "performance-p95":
            row["metrics"] = {"p95_seconds": p95_seconds}
        if row["id"] == "approval-major-risk":
            row["approval"] = {"required": True, "recorded": True}
    return receipt


def test_checked_in_matrix_has_the_required_release_dimensions():
    manifest = load_manifest()
    fixture_ids = {fixture["id"] for fixture in manifest["fixtures"]}
    assert len(manifest["fixtures"]) == 12
    assert {"terminal-session-control", "approval-major-risk", "context-isolation", "parallel-decomposition", "performance-p95"} <= fixture_ids
    assert sum(fixture["weight"] for fixture in manifest["fixtures"]) == 100


def test_full_paired_evidence_passes_and_renders_an_auditable_report():
    manifest = load_manifest()
    result = compare_receipts(
        manifest,
        completed_receipt("obus", manifest, p95_seconds=1.2),
        completed_receipt("codex", manifest, p95_seconds=1.0),
    )

    assert result["summary"]["release_ready"] is True
    assert result["summary"]["weighted_score"] == 100.0
    performance = next(row for row in result["rows"] if row["id"] == "performance-p95")
    assert performance["metric_ratio"] == 1.2
    report = format_markdown(result)
    assert "Release ready: **yes**" in report
    assert "approval-major-risk" in report


def test_critical_approval_fixture_blocks_release_without_a_recorded_approval():
    manifest = load_manifest()
    obus = completed_receipt("obus", manifest)
    codex = completed_receipt("codex", manifest)
    approval = next(row for row in obus["fixtures"] if row["id"] == "approval-major-risk")
    approval["approval"] = {"required": True, "recorded": False}

    result = compare_receipts(manifest, obus, codex)

    assert result["summary"]["release_ready"] is False
    assert result["summary"]["critical_blockers"] == ["approval-major-risk"]
    critical_row = next(row for row in result["rows"] if row["id"] == "approval-major-risk")
    assert "recorded explicit approval" in critical_row["reasons"][0]


def test_missing_evidence_is_incomplete_not_a_silent_pass():
    manifest = load_manifest()
    obus = completed_receipt("obus", manifest)
    codex = completed_receipt("codex", manifest)
    next(row for row in obus["fixtures"] if row["id"] == "context-isolation")["status"] = "not-run"

    result = compare_receipts(manifest, obus, codex)

    assert result["summary"]["release_ready"] is False
    assert "context-isolation" in result["summary"]["incomplete"]


def test_receipt_rejects_unknown_fixture_ids():
    manifest = load_manifest()
    receipt = completed_receipt("obus", manifest)
    receipt["fixtures"].append({"id": "not-a-fixture", "status": "passed", "score": 5, "metrics": {}, "evidence": [], "approval": {}})

    with pytest.raises(MatrixValidationError, match="unknown fixture"):
        compare_receipts(manifest, receipt, completed_receipt("codex", manifest))


def test_plan_only_cli_describes_adapters_without_starting_them():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--plan"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["manifest"]["fixture_count"] == 12
    assert "POST /api/harness/tasks" in plan["adapters"]["obus"]["execution_contract"]
    assert "--approve-for-me" in plan["adapters"]["codex"]["execution_contract"]
