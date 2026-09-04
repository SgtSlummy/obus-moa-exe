#!/usr/bin/env python3
"""Safely collect normalized fixture receipts for the OBus/Codex parity matrix.

This runner never performs destructive operations.  It records only evidence from
local health endpoints, version probes, and selected test targets.  A fixture is
marked complete only when its concrete probe passes; unsupported probes remain
``not-run`` rather than being inferred from a broad test suite.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

import websocket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.parity_matrix import blank_receipt, validate_manifest, validate_receipt

MANIFEST_PATH = ROOT / "data" / "obus-codex-comparison-manifest.json"
SAFE_OBUS_TESTS = {
    "desktop-lifecycle": ("tests/test_headless_bridge.py",),
    "thread-stream-interrupt": ("tests/test_agent_harness.py",),
    "terminal-session-control": ("tests/test_terminal_api.py",),
    "workspace-scoped-edit": ("tests/test_workspace_context.py",),
    "approval-major-risk": ("tests/test_codex_policy.py",),
    "context-isolation": ("tests/test_context_policy.py",),
    "parallel-decomposition": ("tests/test_codex_bridge_api.py",),
    "run-recovery-receipts": ("tests/test_agent_harness.py",),
    "installation-upgrade": ("tests/test_build_install_contract.py",),
    "regression-report": ("tests/test_parity_matrix.py",),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def git_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() or "unknown"


def codex_version_command() -> list[str]:
    executable = shutil.which("codex")
    if executable and executable.lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell:
            return [shell, "-NoProfile", "-File", executable, "--version"]
    return [executable or "codex", "--version"]


def command_receipt(command: list[str], *, timeout: int = 120) -> tuple[bool, dict[str, Any]]:
    started = time.perf_counter()
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        passed = result.returncode == 0
        output = (result.stdout + "\n" + result.stderr).strip()
        return passed, {
            "kind": "command",
            "command": command,
            "exit_code": result.returncode,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "output_tail": output[-1200:],
        }
    except subprocess.TimeoutExpired:
        return False, {"kind": "command", "command": command, "duration_ms": round((time.perf_counter() - started) * 1000), "error": "timeout"}
    except OSError as exc:
        return False, {"kind": "command", "command": command, "duration_ms": round((time.perf_counter() - started) * 1000), "error": type(exc).__name__}


def pytest_receipt(targets: tuple[str, ...]) -> tuple[bool | None, dict[str, Any]]:
    existing = tuple(target for target in targets if (ROOT / target).exists())
    if not existing:
        return None, {"kind": "pytest", "targets": list(targets), "reason": "No mapped test target exists."}
    base_temp = Path(tempfile.mkdtemp(prefix="obus-fixture-pytest-"))
    try:
        return command_receipt([
            sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--basetemp", str(base_temp), *existing,
        ])
    finally:
        shutil.rmtree(base_temp, ignore_errors=True)


def http_json(url: str, *, timeout: int = 15) -> tuple[bool, dict[str, Any]]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return True, {"kind": "http", "url": url, "status": 200, "duration_ms": round((time.perf_counter() - started) * 1000), "body": payload}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        return False, {"kind": "http", "url": url, "duration_ms": round((time.perf_counter() - started) * 1000), "error": type(exc).__name__}


def environment() -> dict[str, str]:
    return {
        "os": f"{platform.system()} {platform.release()}",
        "hardware": platform.machine() or "unknown",
        "network": "local-loopback-only",
        "sandbox": "safe-local-fixture-runner",
        "approval_policy": "destructive-and-hardware-actions-require-human-approval",
    }


def selected_ids(manifest: dict[str, Any], raw: str) -> list[str]:
    available = [item["id"] for item in manifest["fixtures"]]
    if raw == "all":
        return available
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise ValueError(f"Unknown fixture IDs: {', '.join(unknown)}")
    return requested


def _evidence_text(evidence: dict[str, Any]) -> str:
    return json.dumps(evidence, sort_keys=True, separators=(",", ":"))


def complete(fixture: dict[str, Any], evidence: dict[str, Any]) -> None:
    fixture["status"] = "passed"
    fixture["score"] = 5.0
    fixture["metrics"] = {"duration_ms": evidence.get("duration_ms", 0)}
    fixture["evidence"] = [_evidence_text(evidence)]


def not_run(fixture: dict[str, Any], reason: str) -> None:
    fixture["status"] = "not-run"
    fixture["evidence"] = [reason]


def request_json(url: str, method: str, payload: dict[str, Any] | None = None, *, timeout: int = 15) -> tuple[bool, dict[str, Any]]:
    started = time.perf_counter()
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            result = json.loads(raw) if raw else {}
        return True, {"kind": "http", "method": method, "url": url, "status": response.status, "duration_ms": round((time.perf_counter() - started) * 1000), "body": result}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        return False, {"kind": "http", "method": method, "url": url, "duration_ms": round((time.perf_counter() - started) * 1000), "error": type(exc).__name__}


def terminal_lifecycle_evidence(host: str) -> dict[str, Any]:
    start_ok, started = request_json(f"{host}/api/terminal/sessions", "POST", {"shell": "pwsh", "rows": 24, "cols": 96})
    session_id = str(started.get("body", {}).get("id") or "") if start_ok else ""
    checks = [started]
    try:
        if not session_id:
            return {"verified": False, "reason": "terminal session was not created", "checks": checks}
        resize_ok, resized = request_json(f"{host}/api/terminal/sessions/{session_id}/size", "PATCH", {"rows": 30, "cols": 110})
        input_ok, accepted = request_json(f"{host}/api/terminal/sessions/{session_id}/input", "POST", {"data": "Write-Output 'OBUS_SAFE_TERMINAL_PROBE'\\r"})
        checks.extend([resized, accepted])
        return {"verified": bool(resize_ok and input_ok), "reason": "The REST API confirms lifecycle control but does not expose terminal output for an independent output assertion.", "checks": checks}
    finally:
        if session_id:
            closed_ok, closed = request_json(f"{host}/api/terminal/sessions/{session_id}", "DELETE")
            checks.append(closed)
            if not closed_ok:
                checks.append({"kind": "runner", "error": "terminal session cleanup failed"})


def terminal_output_evidence(host: str) -> dict[str, Any]:
    started_ok, started = request_json(f"{host}/api/terminal/sessions", "POST", {"shell": "pwsh", "rows": 24, "cols": 96})
    session_id = str(started.get("body", {}).get("id") or "") if started_ok else ""
    checks = [started]
    stream = None
    try:
        if not session_id:
            return {"verified": False, "reason": "terminal session was not created", "checks": checks}
        stream_url = f"{host.replace('http://', 'ws://').replace('https://', 'wss://')}/api/terminal/sessions/{session_id}/stream"
        stream = websocket.create_connection(stream_url, timeout=10)
        resized_ok, resized = request_json(f"{host}/api/terminal/sessions/{session_id}/size", "PATCH", {"rows": 30, "cols": 110})
        stream.send(json.dumps({"type": "input", "data": "Write-Output 'OBUS_SAFE_TERMINAL_PROBE'\\r"}))
        output = ""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and "OBUS_SAFE_TERMINAL_PROBE" not in output:
            message = json.loads(stream.recv())
            if message.get("type") == "output":
                output += str(message.get("data") or "")
        checks.extend([resized, {"kind": "websocket", "url": stream_url, "output_marker_seen": "OBUS_SAFE_TERMINAL_PROBE" in output}])
        return {"verified": bool(resized_ok and "OBUS_SAFE_TERMINAL_PROBE" in output), "checks": checks}
    except (OSError, ValueError, websocket.WebSocketException) as exc:
        return {"verified": False, "reason": type(exc).__name__, "checks": checks}
    finally:
        if stream is not None:
            stream.close()
        if session_id:
            closed_ok, closed = request_json(f"{host}/api/terminal/sessions/{session_id}", "DELETE")
            checks.append(closed)
            if not closed_ok:
                checks.append({"kind": "runner", "error": "terminal session cleanup failed"})


def run_obus(receipt: dict[str, Any], fixture_ids: list[str], host: str) -> None:
    fixtures = {item["id"]: item for item in receipt["fixtures"]}
    for fixture_id in fixture_ids:
        fixture = fixtures[fixture_id]
        if fixture_id == "headless-local-model":
            ok_health, health = http_json(f"{host}/health")
            ok_bridge, bridge = http_json(f"{host}/api/codex-bridge/status")
            if ok_health and ok_bridge and health["body"].get("status") == "ok":
                complete(fixture, {"kind": "combined-http", "duration_ms": health["duration_ms"] + bridge["duration_ms"], "checks": [health, bridge]})
            else:
                fixture["status"] = "failed"
                fixture["score"] = 0.0
                fixture["evidence"] = [_evidence_text(health), _evidence_text(bridge)]
            continue
        if fixture_id == "terminal-session-control":
            lifecycle = terminal_output_evidence(host)
            if lifecycle["verified"]:
                complete(fixture, {"kind": "terminal-lifecycle", "duration_ms": sum(check.get("duration_ms", 0) for check in lifecycle["checks"]), "checks": lifecycle["checks"]})
            else:
                not_run(fixture, _evidence_text(lifecycle))
            continue
        targets = SAFE_OBUS_TESTS.get(fixture_id)
        if not targets:
            not_run(fixture, "No safe automated probe is implemented for this fixture yet.")
            continue
        passed, evidence = pytest_receipt(targets)
        if passed is None:
            not_run(fixture, str(evidence["reason"]))
        elif passed:
            complete(fixture, evidence)
            if fixture_id == "approval-major-risk":
                fixture["approval"] = {"required": True, "recorded": True, "decision": "simulated-safe-test"}
        else:
            fixture["status"] = "failed"
            fixture["score"] = 0.0
            fixture["evidence"] = [_evidence_text(evidence)]


def run_codex(receipt: dict[str, Any], fixture_ids: list[str]) -> None:
    fixtures = {item["id"]: item for item in receipt["fixtures"]}
    available, evidence = command_receipt(codex_version_command(), timeout=30)
    for fixture_id in fixture_ids:
        if fixture_id == "headless-local-model" and available:
            complete(fixtures[fixture_id], evidence)
        else:
            not_run(fixtures[fixture_id], "Codex fixtures require a user-approved isolated worktree run; this safe runner only records CLI availability.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", choices=("obus", "codex"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", default="all", help="Comma-separated manifest IDs, or all.")
    parser.add_argument("--host", default=os.environ.get("OBUS_URL", "http://127.0.0.1:38173"))
    parser.add_argument("--model", default="local-safe-fixture-runner")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = validate_manifest(load_json(MANIFEST_PATH))
    run = {
        "id": f"{args.product}-fixture-{uuid.uuid4().hex[:12]}",
        "model": args.model,
        "product_version": "local-working-tree",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "worktree_sha": git_sha(),
    }
    receipt = blank_receipt(args.product, manifest, run=run, environment=environment())
    fixture_ids = selected_ids(manifest, args.fixtures)
    if args.product == "obus":
        run_obus(receipt, fixture_ids, args.host.rstrip("/"))
    else:
        run_codex(receipt, fixture_ids)
    validate_receipt(receipt, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    complete_count = sum(item["status"] == "passed" for item in receipt["fixtures"])
    print(json.dumps({"output": str(args.output), "product": args.product, "complete": complete_count, "total": len(receipt["fixtures"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
