#!/usr/bin/env python3
"""Generate and score the auditable OBus-versus-Codex parity matrix.

Default operation is plan-only: it reads a checked-in manifest and writes
nothing.  Product adapters or human verifiers supply two normalized receipts;
this utility then applies the same rubric and release gates to both products.

Examples:
  python scripts/obus_codex_comparison.py --plan
  python scripts/obus_codex_comparison.py --obus-receipt obus.json --codex-receipt codex.json --output comparison.json --markdown-output comparison.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.codex_policy import build_codex_exec_command
from backend.parity_matrix import (
    MatrixValidationError,
    blank_receipt,
    compare_receipts,
    format_markdown,
    validate_manifest,
)


DEFAULT_MANIFEST = ROOT / "data" / "obus-codex-comparison-manifest.json"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixValidationError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise MatrixValidationError(f"JSON root in {path} must be an object")
    return value


def adapter_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    """Describe the two receipt producers without starting agents or shells."""

    return {
        "manifest": {
            "schema_version": manifest["schema_version"],
            "fixture_count": len(manifest["fixtures"]),
            "fixture_ids": [fixture["id"] for fixture in manifest["fixtures"]],
        },
        "adapters": {
            "codex": {
                "execution_contract": "codex exec --approve-for-me in an isolated worktree",
                "command_builder": "backend.codex_policy.build_codex_exec_command",
                "receipt_contract": "Record run metadata, verifier score, metrics, evidence paths, and approval state; never record raw prompts or provider secrets.",
            },
            "obus": {
                "execution_contract": "POST /api/harness/tasks with provider=codex in an isolated worktree",
                "status_contract": "Poll GET /api/harness/tasks/{task_id} until succeeded, failed, or cancelled.",
                "receipt_contract": "Use the same fixture ID and verifier rubric as Codex; preserve OBus receipts separately from comparison evidence.",
            },
        },
        "comparability_requirements": [
            "same fixture manifest and baseline worktree hash",
            "separate clean worktrees for OBus and Codex",
            "record OS, hardware, sandbox, approval policy, network setting, model, and product version",
            "do not treat process completion as task-quality success; a verifier assigns the score",
        ],
    }


def receipt_template(product: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Emit a template which adapters can populate after an actual run."""

    return blank_receipt(
        product,
        manifest,
        run={
            "id": f"replace-{product}-run-id",
            "started_at": "replace-with-ISO-8601",
            "worktree_sha": "replace-with-baseline-git-sha",
            "model": "replace-with-model",
            "product_version": "replace-with-version",
        },
        environment={
            "os": "replace-with-os-version",
            "hardware": "replace-with-cpu-gpu-ram",
            "sandbox": "replace-with-sandbox-policy",
            "approval_policy": "replace-with-approval-policy",
            "network": "replace-with-network-policy",
        },
    )


def codex_command_preview(prompt: str, *, model: str | None = None) -> list[str]:
    """Expose the exact safe command shape used by a future Codex adapter."""

    return build_codex_exec_command("codex", prompt, model=model)


def write_json(path: Path, value: MappingLike) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


MappingLike = dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="matrix manifest JSON")
    parser.add_argument("--plan", action="store_true", help="print the adapter and fixture plan (default when no receipts are supplied)")
    parser.add_argument("--template", choices=("obus", "codex"), help="print an empty normalized receipt template")
    parser.add_argument("--obus-receipt", type=Path, help="completed normalized OBus receipt JSON")
    parser.add_argument("--codex-receipt", type=Path, help="completed normalized Codex receipt JSON")
    parser.add_argument("--output", type=Path, help="write the scored JSON report")
    parser.add_argument("--markdown-output", type=Path, help="write the scored Markdown report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = validate_manifest(load_json(args.manifest))
        if args.template:
            print(json.dumps(receipt_template(args.template, manifest), indent=2, sort_keys=True))
            return 0

        supplied = bool(args.obus_receipt or args.codex_receipt)
        if supplied and not (args.obus_receipt and args.codex_receipt):
            raise MatrixValidationError("--obus-receipt and --codex-receipt must be supplied together")
        if not supplied:
            print(json.dumps(adapter_contract(manifest), indent=2, sort_keys=True))
            return 0

        result = compare_receipts(
            manifest,
            load_json(args.obus_receipt),
            load_json(args.codex_receipt),
        )
        if args.output:
            write_json(args.output, result)
        report = format_markdown(result)
        if args.markdown_output:
            args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_output.write_text(report, encoding="utf-8")
        print(report, end="")
        return 0 if result["summary"]["release_ready"] else 2
    except MatrixValidationError as exc:
        print(f"comparison matrix error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
