#!/usr/bin/env python3
"""Aggregate independent Hermetic Atelier visual reviews without rounding up."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from typing import Any


WEIGHTS = {
    "geometry": 20,
    "typography": 12,
    "golden_ratio": 10,
    "spacing": 10,
    "responsive": 12,
    "accessibility": 12,
    "adjustability": 10,
    "identity": 8,
    "polish": 3,
    "stability": 3,
}
RELEASE_THRESHOLD = 9.90
CATEGORY_FLOOR = 9.70


def truncate_two(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def _validate_reviews(reviews: list[dict[str, Any]]) -> None:
    if len(reviews) < 2:
        raise ValueError("at least two fresh reviews are required")
    reviewer_ids = [str(review.get("reviewer_id") or "") for review in reviews]
    if not all(reviewer_ids) or len(set(reviewer_ids)) != len(reviewer_ids):
        raise ValueError("reviewer_id values must be non-empty and unique")
    expected = set(WEIGHTS)
    for review in reviews:
        scores = review.get("category_scores") or {}
        if set(scores) != expected:
            raise ValueError(f"review categories must exactly match: {sorted(expected)}")
        for key, raw in scores.items():
            value = float(raw)
            if not math.isfinite(value) or not 0 <= value <= 10:
                raise ValueError(f"invalid score for {key}: {raw}")
        evidence = review.get("evidence_paths") or []
        if not evidence or not all(isinstance(path, str) and path for path in evidence):
            raise ValueError("each reviewer must cite at least one evidence path")


def _weighted_score(review: dict[str, Any]) -> float:
    scores = review["category_scores"]
    return sum(float(scores[key]) * weight for key, weight in WEIGHTS.items()) / 100


def aggregate_reviews(
    reviews: list[dict[str, Any]], *, hard_gates_pass: bool
) -> dict[str, Any]:
    _validate_reviews(reviews)
    category_means = {
        key: statistics.fmean(float(review["category_scores"][key]) for review in reviews)
        for key in WEIGHTS
    }
    category_pstdev = {
        key: statistics.pstdev(float(review["category_scores"][key]) for review in reviews)
        for key in WEIGHTS
    }
    reviewer_weighted_scores = {
        review["reviewer_id"]: _weighted_score(review) for review in reviews
    }
    weighted_mean = statistics.fmean(reviewer_weighted_scores.values())
    blockers: list[str] = []
    if not hard_gates_pass:
        blockers.append("hard_gates")
    if weighted_mean < RELEASE_THRESHOLD:
        blockers.append("weighted_threshold")
    for key, value in category_means.items():
        if value < CATEGORY_FLOOR:
            blockers.append(f"category_floor:{key}")
    return {
        "schema": "obus-aui-review-aggregate-v1",
        "reviewer_count": len(reviews),
        "reviewer_ids": [review["reviewer_id"] for review in reviews],
        "hard_gates_pass": bool(hard_gates_pass),
        "weights": WEIGHTS,
        "reviewer_weighted_scores": reviewer_weighted_scores,
        "reviewer_weighted_pstdev": statistics.pstdev(reviewer_weighted_scores.values()),
        "category_means": category_means,
        "category_pstdev": category_pstdev,
        "weighted_mean": weighted_mean,
        "weighted_display_truncated": truncate_two(weighted_mean),
        "release_threshold": RELEASE_THRESHOLD,
        "category_floor": CATEGORY_FLOOR,
        "blockers": blockers,
        "pass": not blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON containing reviews and hard_gates_pass")
    parser.add_argument("--out", type=Path, help="Optional aggregate output path")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result = aggregate_reviews(
        payload.get("reviews") or [], hard_gates_pass=bool(payload.get("hard_gates_pass"))
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
