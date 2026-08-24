#!/usr/bin/env python3
"""Emit a safe OBus benchmark matrix and optionally collect local read-only status.

This utility deliberately does not run deliberations or warm models. A future
write-capable load runner should be a separate, explicitly gated tool.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OBUS_DEFAULT = "http://127.0.0.1:38173"
OLLAMA_DEFAULT = "http://127.0.0.1:11434"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_get(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(base_url.rstrip("/") + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            body: Any
            try:
                body = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {"text_length": len(raw)}
            return {
                "ok": True,
                "status": response.status,
                "seconds": round(time.perf_counter() - started, 6),
                "body": body,
            }
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "ok": False,
            "status": None,
            "seconds": round(time.perf_counter() - started, 6),
            "error": type(exc).__name__,
        }


def nvidia_smi_probe() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "reason": "nvidia-smi-not-found"}
    query = ",".join(
        [
            "timestamp",
            "name",
            "driver_version",
            "utilization.gpu",
            "utilization.memory",
            "memory.used",
            "memory.total",
            "temperature.gpu",
            "power.draw",
        ]
    )
    try:
        result = subprocess.run(
            [executable, f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": type(exc).__name__}
    output = (result.stdout or "").strip()
    return {
        "available": result.returncode == 0,
        "return_code": result.returncode,
        "rows": output.splitlines() if result.returncode == 0 else [],
        "error": (result.stderr or "").strip()[-500:] if result.returncode else None,
    }


def benchmark_matrix() -> dict[str, Any]:
    return {
        "deliberation_latency": {
            "cases": ["short-circuit", "council-short", "council-medium", "council-long"],
            "modes": ["collaborative", "adversarial"],
            "cards": [2, 4, 8],
            "profiles": ["fast", "balanced", "deep", "throughput"],
            "warmups": 3,
            "measured_repetitions": 20,
            "metrics": [
                "wall_seconds",
                "planning_seconds",
                "deliberation_seconds",
                "local_generation_seconds",
                "aggregation_seconds",
                "p50",
                "p90",
                "p95",
                "p99",
                "error_rate",
            ],
        },
        "room_concurrency": {
            "different_rooms_concurrency": [1, 2, 4, 8],
            "same_room_concurrency": 2,
            "forum_room_counts": [2, 4, 8],
            "expected_same_room_status": 409,
            "expected_same_forum_status": 409,
            "metrics": ["completed", "status_409", "status_4xx", "status_5xx", "throughput", "p95"],
        },
        "ollama_gpu": {
            "read_only_endpoints": ["/api/tags", "/api/ps"],
            "external_sampler": "nvidia-smi",
            "sample_interval_seconds": 1.0,
            "conditions": ["cold-residency", "warm-residency", "concurrent-requests", "context-size-sweep"],
            "metrics": [
                "load_duration",
                "total_duration",
                "prompt_eval_duration",
                "eval_duration",
                "prompt_eval_count",
                "eval_count",
                "size_vram",
                "gpu_utilization",
                "gpu_memory_used",
            ],
        },
        "warp_preprocessing": {
            "scope": "independent-preprocessing-fixture-only",
            "devices": ["cpu", "cuda:0"],
            "comparators": ["cpu-reference", "warp-cpu", "warp-cuda"],
            "warmups": 3,
            "measured_repetitions": 50,
            "measure_separately": [
                "input_creation",
                "host_to_device",
                "first_kernel_compile",
                "steady_state_kernel",
                "device_to_host",
            ],
            "explicit_nonclaim": "Do not report as transformer inference acceleration.",
        },
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "mode": "read-only-probe" if args.probe else "plan-only",
        "safety": {
            "writes_enabled": False,
            "remote_execution": False,
            "model_pull": False,
            "warmup_requested": False,
            "warp_launch_requested": False,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "plan": benchmark_matrix(),
    }
    if not args.probe:
        return report

    report["probe"] = {
        "obus": {
            path: http_get(args.obus_url, path, args.timeout)
            for path in ("/health", "/api/dashboard", "/api/warmup", "/api/integrations/warp")
        },
        "ollama": {
            path: http_get(args.ollama_url, path, args.timeout)
            for path in ("/api/tags", "/api/ps")
        },
        "nvidia_smi": nvidia_smi_probe(),
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="collect local read-only service/GPU status")
    parser.add_argument("--obus-url", default=OBUS_DEFAULT, help=f"OBus base URL (default: {OBUS_DEFAULT})")
    parser.add_argument("--ollama-url", default=OLLAMA_DEFAULT, help=f"Ollama base URL (default: {OLLAMA_DEFAULT})")
    parser.add_argument("--timeout", type=float, default=3.0, help="read-only HTTP timeout in seconds")
    parser.add_argument("--output", type=Path, help="write JSON report to this path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
