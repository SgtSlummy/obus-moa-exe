"""Data contracts and scoring for repeatable OBus-versus-Codex comparisons.

The comparison layer deliberately separates an agent's execution receipt from
its assessment.  A completed process is useful evidence, but it is not proof
that a coding task was solved correctly.  Adapters therefore emit receipts and
verifiers assign the 0--5 fixture score used by this module.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping


SCHEMA_VERSION = 1
PRODUCTS = frozenset({"obus", "codex"})
STATUSES = frozenset({"passed", "failed", "blocked", "not-run"})


class MatrixValidationError(ValueError):
    """Raised when a matrix manifest or comparison receipt is invalid."""


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MatrixValidationError(f"{name} must be an object")
    return value


def _number(value: Any, name: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool):
        raise MatrixValidationError(f"{name} must be a number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MatrixValidationError(f"{name} must be a number") from exc
    if not minimum <= number <= maximum:
        raise MatrixValidationError(f"{name} must be between {minimum:g} and {maximum:g}")
    return number


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a detached comparison matrix manifest.

    A manifest defines fixtures and release gates only.  It contains no prompts
    with secrets and never makes a network call.
    """

    source = _require_mapping(manifest, "manifest")
    normalized = deepcopy(dict(source))
    if normalized.get("schema_version") != SCHEMA_VERSION:
        raise MatrixValidationError(f"schema_version must be {SCHEMA_VERSION}")
    if set(normalized.get("products", ())) != PRODUCTS:
        raise MatrixValidationError("products must contain exactly obus and codex")

    scale = _require_mapping(normalized.get("score_scale"), "score_scale")
    minimum = _number(scale.get("minimum"), "score_scale.minimum", -1000, 1000)
    maximum = _number(scale.get("maximum"), "score_scale.maximum", minimum + 0.0001, 1000)
    _number(scale.get("tolerance_points"), "score_scale.tolerance_points", 0, maximum - minimum)

    gates = _require_mapping(normalized.get("release_gates"), "release_gates")
    _number(gates.get("weighted_score_min"), "release_gates.weighted_score_min", 0, 100)
    _number(gates.get("domain_score_min"), "release_gates.domain_score_min", 0, 100)

    fixtures = normalized.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise MatrixValidationError("fixtures must be a non-empty list")
    seen: set[str] = set()
    total_weight = 0.0
    for index, raw_fixture in enumerate(fixtures):
        fixture = _require_mapping(raw_fixture, f"fixtures[{index}]")
        fixture_id = fixture.get("id")
        if not isinstance(fixture_id, str) or not fixture_id.strip():
            raise MatrixValidationError(f"fixtures[{index}].id must be a non-empty string")
        if fixture_id in seen:
            raise MatrixValidationError(f"duplicate fixture id: {fixture_id}")
        seen.add(fixture_id)
        for field in ("dimension", "title", "fixture", "pass_criterion"):
            if not isinstance(fixture.get(field), str) or not fixture[field].strip():
                raise MatrixValidationError(f"fixtures[{index}].{field} must be a non-empty string")
        total_weight += _number(fixture.get("weight"), f"fixtures[{index}].weight", 0.0001, 10000)
        if not isinstance(fixture.get("critical", False), bool):
            raise MatrixValidationError(f"fixtures[{index}].critical must be boolean")
        comparison = fixture.get("comparison", {})
        if comparison:
            comparison = _require_mapping(comparison, f"fixtures[{index}].comparison")
            metric = comparison.get("metric")
            if not isinstance(metric, str) or not metric:
                raise MatrixValidationError(f"fixtures[{index}].comparison.metric must be a string")
            _number(comparison.get("max_ratio"), f"fixtures[{index}].comparison.max_ratio", 0.0001, 1000000)
    if total_weight <= 0:
        raise MatrixValidationError("fixtures must have positive total weight")
    return normalized


def validate_receipt(receipt: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a normalized product receipt against a matrix manifest."""

    matrix = validate_manifest(manifest)
    source = _require_mapping(receipt, "receipt")
    normalized = deepcopy(dict(source))
    if normalized.get("schema_version") != SCHEMA_VERSION:
        raise MatrixValidationError(f"receipt.schema_version must be {SCHEMA_VERSION}")
    if normalized.get("product") not in PRODUCTS:
        raise MatrixValidationError("receipt.product must be obus or codex")
    run = _require_mapping(normalized.get("run"), "receipt.run")
    for field in ("id", "started_at", "worktree_sha", "model", "product_version"):
        if not isinstance(run.get(field), str) or not run[field].strip():
            raise MatrixValidationError(f"receipt.run.{field} must be a non-empty string")
    environment = _require_mapping(normalized.get("environment"), "receipt.environment")
    for field in ("os", "hardware", "sandbox", "approval_policy", "network"):
        if not isinstance(environment.get(field), str) or not environment[field].strip():
            raise MatrixValidationError(f"receipt.environment.{field} must be a non-empty string")

    known_ids = {fixture["id"] for fixture in matrix["fixtures"]}
    fixture_rows = normalized.get("fixtures")
    if not isinstance(fixture_rows, list):
        raise MatrixValidationError("receipt.fixtures must be a list")
    seen: set[str] = set()
    minimum = float(matrix["score_scale"]["minimum"])
    maximum = float(matrix["score_scale"]["maximum"])
    for index, raw_row in enumerate(fixture_rows):
        row = _require_mapping(raw_row, f"receipt.fixtures[{index}]")
        fixture_id = row.get("id")
        if fixture_id not in known_ids:
            raise MatrixValidationError(f"receipt references unknown fixture: {fixture_id}")
        if fixture_id in seen:
            raise MatrixValidationError(f"receipt repeats fixture: {fixture_id}")
        seen.add(fixture_id)
        if row.get("status") not in STATUSES:
            raise MatrixValidationError(f"receipt fixture {fixture_id} has invalid status")
        if row.get("status") in {"passed", "failed"}:
            _number(row.get("score"), f"receipt fixture {fixture_id}.score", minimum, maximum)
        elif row.get("score") is not None:
            _number(row["score"], f"receipt fixture {fixture_id}.score", minimum, maximum)
        metrics = row.get("metrics", {})
        _require_mapping(metrics, f"receipt fixture {fixture_id}.metrics")
        evidence = row.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(item, str) and item for item in evidence):
            raise MatrixValidationError(f"receipt fixture {fixture_id}.evidence must be a list of non-empty strings")
        approval = row.get("approval", {})
        _require_mapping(approval, f"receipt fixture {fixture_id}.approval")
        for field in ("required", "recorded"):
            if field in approval and not isinstance(approval[field], bool):
                raise MatrixValidationError(f"receipt fixture {fixture_id}.approval.{field} must be boolean")
    return normalized


def blank_receipt(product: str, manifest: Mapping[str, Any], *, run: Mapping[str, str], environment: Mapping[str, str]) -> dict[str, Any]:
    """Create a non-passing receipt template for a product adapter or verifier."""

    matrix = validate_manifest(manifest)
    if product not in PRODUCTS:
        raise MatrixValidationError("product must be obus or codex")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "product": product,
        "run": dict(run),
        "environment": dict(environment),
        "fixtures": [
            {
                "id": fixture["id"],
                "status": "not-run",
                "metrics": {},
                "evidence": [],
                "approval": {},
            }
            for fixture in matrix["fixtures"]
        ],
    }
    return validate_receipt(receipt, matrix)


def _fixture_lookup(receipt: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {row["id"]: row for row in receipt["fixtures"]}


def _metric_ratio(obus: Mapping[str, Any], codex: Mapping[str, Any], metric: str) -> float | None:
    obus_value = obus.get("metrics", {}).get(metric)
    codex_value = codex.get("metrics", {}).get(metric)
    if obus_value is None or codex_value is None:
        return None
    denominator = _number(codex_value, f"codex metric {metric}", 0.000001, 1_000_000_000)
    numerator = _number(obus_value, f"obus metric {metric}", 0, 1_000_000_000)
    return round(numerator / denominator, 4)


def compare_receipts(manifest: Mapping[str, Any], obus_receipt: Mapping[str, Any], codex_receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Score OBus against Codex and apply manifest release gates.

    Scores come from an explicit verifier.  Missing or blocked fixtures are
    deliberately incomplete rather than silently counted as successes.
    """

    matrix = validate_manifest(manifest)
    obus = validate_receipt(obus_receipt, matrix)
    codex = validate_receipt(codex_receipt, matrix)
    if obus["product"] != "obus" or codex["product"] != "codex":
        raise MatrixValidationError("compare_receipts requires an obus and a codex receipt")

    minimum = float(matrix["score_scale"]["minimum"])
    maximum = float(matrix["score_scale"]["maximum"])
    tolerance = float(matrix["score_scale"]["tolerance_points"])
    obus_rows = _fixture_lookup(obus)
    codex_rows = _fixture_lookup(codex)
    rows: list[dict[str, Any]] = []
    domain_totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    total_weight = sum(float(fixture["weight"]) for fixture in matrix["fixtures"])
    weighted_points = 0.0
    measured_weight = 0.0
    blockers: list[str] = []

    for fixture in matrix["fixtures"]:
        fixture_id = fixture["id"]
        obus_row = obus_rows.get(fixture_id, {"status": "not-run", "metrics": {}, "approval": {}})
        codex_row = codex_rows.get(fixture_id, {"status": "not-run", "metrics": {}, "approval": {}})
        weight = float(fixture["weight"])
        dimension = fixture["dimension"]
        status = "incomplete"
        reasons: list[str] = []
        ratio: float | None = None

        if obus_row.get("status") not in {"passed", "failed"} or codex_row.get("status") not in {"passed", "failed"}:
            reasons.append("both product receipts need a passed or failed verified result")
        else:
            obus_score = float(obus_row["score"])
            codex_score = float(codex_row["score"])
            measured_weight += weight
            normalized_score = (obus_score - minimum) / (maximum - minimum)
            weighted_points += weight * normalized_score
            domain_totals[dimension][0] += weight * normalized_score
            domain_totals[dimension][1] += weight
            if obus_score < codex_score - tolerance:
                reasons.append(f"OBus score {obus_score:g} is more than {tolerance:g} below Codex {codex_score:g}")
            comparison = fixture.get("comparison", {})
            if comparison:
                ratio = _metric_ratio(obus_row, codex_row, comparison["metric"])
                if ratio is None:
                    reasons.append(f"both receipts need metric {comparison['metric']}")
                elif ratio > float(comparison["max_ratio"]):
                    reasons.append(f"OBus/Codex {comparison['metric']} ratio {ratio:g} exceeds {comparison['max_ratio']:g}")
            if fixture.get("critical"):
                approval = obus_row.get("approval", {})
                if approval.get("required") is not True or approval.get("recorded") is not True:
                    reasons.append("critical safety fixture lacks recorded explicit approval")
            status = "pass" if not reasons and obus_row.get("status") == "passed" else "fail"
            if obus_row.get("status") != "passed":
                reasons.append("OBus verifier did not pass this fixture")
                status = "fail"

        if fixture.get("critical") and status != "pass":
            blockers.append(fixture_id)
        rows.append(
            {
                "id": fixture_id,
                "dimension": dimension,
                "title": fixture["title"],
                "weight": weight,
                "critical": bool(fixture.get("critical")),
                "status": status,
                "obus_status": obus_row.get("status", "not-run"),
                "codex_status": codex_row.get("status", "not-run"),
                "obus_score": obus_row.get("score"),
                "codex_score": codex_row.get("score"),
                "metric_ratio": ratio,
                "reasons": reasons,
            }
        )

    weighted_score = round((weighted_points / total_weight) * 100, 2)
    coverage_percent = round((measured_weight / total_weight) * 100, 2)
    domains = {
        name: round((points / weight) * 100, 2)
        for name, (points, weight) in sorted(domain_totals.items()) if weight
    }
    gates = matrix["release_gates"]
    low_domains = [name for name, score in domains.items() if score < float(gates["domain_score_min"])]
    incomplete = [row["id"] for row in rows if row["status"] == "incomplete"]
    failed = [row["id"] for row in rows if row["status"] == "fail"]
    release_ready = not blockers and not incomplete and not failed and weighted_score >= float(gates["weighted_score_min"]) and not low_domains
    return {
        "schema_version": SCHEMA_VERSION,
        "products": {"obus": obus["run"], "codex": codex["run"]},
        "environment_match": {
            field: obus["environment"].get(field) == codex["environment"].get(field)
            for field in ("os", "hardware", "sandbox", "approval_policy", "network")
        },
        "rows": rows,
        "summary": {
            "weighted_score": weighted_score,
            "coverage_percent": coverage_percent,
            "domain_scores": domains,
            "critical_blockers": blockers,
            "failed": failed,
            "incomplete": incomplete,
            "low_domains": low_domains,
            "release_ready": release_ready,
        },
    }


def format_markdown(result: Mapping[str, Any]) -> str:
    """Render a compact, auditable Markdown report from ``compare_receipts``."""

    summary = result["summary"]
    lines = [
        "# OBus vs Codex comparison report",
        "",
        f"Release ready: **{'yes' if summary['release_ready'] else 'no'}**",
        f"Weighted OBus score: **{summary['weighted_score']:.2f}%**",
        f"Measured coverage: **{summary['coverage_percent']:.2f}%**",
        "",
        "| Fixture | OBus | Codex | Score | Status | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in result["rows"]:
        score = f"{row['obus_score']} / {row['codex_score']}"
        if row["metric_ratio"] is not None:
            score += f"; ratio {row['metric_ratio']}"
        notes = "; ".join(row["reasons"]) or "verified"
        lines.append(
            f"| {row['id']} | {row['obus_status']} | {row['codex_status']} | {score} | {row['status']} | {notes} |"
        )
    if summary["critical_blockers"]:
        lines.extend(["", "Critical blockers: " + ", ".join(summary["critical_blockers"])])
    if summary["incomplete"]:
        lines.extend(["", "Incomplete: " + ", ".join(summary["incomplete"])])
    return "\n".join(lines) + "\n"
