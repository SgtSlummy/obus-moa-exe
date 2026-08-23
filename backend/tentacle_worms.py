"""Bounded local startup red-team and hardening workflow for OBus."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

WORM_ROLES = (
    "Scout Worm",
    "Red-Team Worm",
    "Hardener Worm",
    "Verifier Worm",
)

_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+\-/=]{8,}"), r"\1 [REDACTED]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|gh[opusr]_[A-Za-z0-9_]{12,}|nvapi-[A-Za-z0-9_-]{12,})\b"), "[REDACTED]"),
    (re.compile(r"(?i)(api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*\S+"), r"\1: [REDACTED]"),
)


def redact_text(value: str) -> str:
    text = str(value)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value[:50]]
    if isinstance(value, dict):
        clean = {}
        for key, item in list(value.items())[:100]:
            lowered = str(key).lower()
            if lowered in {"api_key", "token", "password", "secret", "authorization"}:
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = redact_value(item)
        return clean
    return value


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _is_loopback(url: str) -> bool:
    host = (urlparse(str(url)).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def run_tentacle_audit(
    *,
    data_dir: Path,
    state: dict[str, Any],
    ollama: dict[str, Any],
    report_file: Path,
    first_install: bool,
    apply_safe_fixes: bool,
    llm_review: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Inspect, safely repair, red-team, and verify one OBus startup.

    Model output is advisory only. Only the deterministic allowlisted repairs in
    this function can modify local state.
    """
    data_dir = Path(data_dir)
    memory_file = data_dir / "memory.json"
    checks: list[dict[str, Any]] = []
    fixes: list[dict[str, str]] = []

    data_dir.mkdir(parents=True, exist_ok=True)
    checks.append({"id": "data_directory", "worm": "Scout Worm", "status": "pass", "severity": "info", "detail": str(data_dir)})

    memory_valid = False
    if memory_file.is_file():
        try:
            memory_valid = isinstance(json.loads(memory_file.read_text(encoding="utf-8")), list)
        except (OSError, UnicodeError, json.JSONDecodeError):
            memory_valid = False
    if not memory_valid and apply_safe_fixes:
        _atomic_json(memory_file, [])
        fixes.append({"id": "repair_memory_json", "detail": "Replaced missing or malformed local memory with an empty list."})
        memory_valid = True
    checks.append({"id": "memory_json", "worm": "Hardener Worm", "status": "pass" if memory_valid else "fail", "severity": "high", "detail": "valid list" if memory_valid else "missing or malformed"})

    settings = state.setdefault("settings", {})
    rag_budget = int(settings.get("rag_character_budget", 2400) or 2400)
    clamped_rag = min(max(rag_budget, 800), 8000)
    if rag_budget != clamped_rag and apply_safe_fixes:
        settings["rag_character_budget"] = clamped_rag
        fixes.append({"id": "clamp_rag_budget", "detail": f"Set RAG budget to {clamped_rag}."})
    parallel = int(settings.get("max_parallel_agents", 5) or 5)
    clamped_parallel = min(max(parallel, 1), 20)
    if parallel != clamped_parallel and apply_safe_fixes:
        settings["max_parallel_agents"] = clamped_parallel
        fixes.append({"id": "clamp_parallel_agents", "detail": f"Set parallel-agent limit to {clamped_parallel}."})
    checks.extend([
        {"id": "rag_budget_bounded", "worm": "Hardener Worm", "status": "pass" if 800 <= int(settings.get("rag_character_budget", rag_budget)) <= 8000 else "fail", "severity": "medium", "detail": str(settings.get("rag_character_budget", rag_budget))},
        {"id": "parallelism_bounded", "worm": "Hardener Worm", "status": "pass" if 1 <= int(settings.get("max_parallel_agents", parallel)) <= 20 else "fail", "severity": "medium", "detail": str(settings.get("max_parallel_agents", parallel))},
    ])

    connected = bool(ollama.get("connected"))
    checks.append({"id": "ollama_connected", "worm": "Scout Worm", "status": "pass" if connected else "fail", "severity": "high", "detail": redact_text(ollama.get("error") or ollama.get("url") or "offline")})
    checks.append({"id": "ollama_loopback", "worm": "Red-Team Worm", "status": "pass" if _is_loopback(ollama.get("url", "")) else "warn", "severity": "medium", "detail": str(ollama.get("url", ""))})
    selected_model = str(settings.get("selected_model", "")).strip()
    models = {str(model) for model in ollama.get("models", [])}
    model_was_missing = not (selected_model and selected_model in models)
    if model_was_missing and models and apply_safe_fixes:
        selected_model = sorted(models, key=lambda value: (value != "gpt-oss:20b", value))[0]
        settings["selected_model"] = selected_model
        fixes.append({"id": "select_installed_local_model", "detail": f"Selected installed local model {selected_model}."})
    model_ready = bool(selected_model and selected_model in models)
    checks.append({"id": "selected_model_missing" if model_was_missing else "selected_model_ready", "worm": "Verifier Worm", "status": "pass" if model_ready else "fail", "severity": "high", "detail": (f"repaired to {selected_model}" if model_was_missing and model_ready else selected_model or "not selected")})

    keys = state.get("keys", []) if isinstance(state.get("keys", []), list) else []
    raw_secret_fields = []
    for key in keys:
        if not isinstance(key, dict):
            continue
        for field in ("api_key", "token", "password", "secret", "authorization"):
            if key.get(field):
                raw_secret_fields.append(f"{key.get('id', 'unknown')}:{field}")
                if apply_safe_fixes:
                    key.pop(field, None)
    if raw_secret_fields and apply_safe_fixes:
        fixes.append({"id": "remove_inline_provider_secrets", "detail": "Removed inline credential values; authorization references remain."})
    checks.append({"id": "provider_credentials_reference_only", "worm": "Red-Team Worm", "status": "pass" if not raw_secret_fields or apply_safe_fixes else "fail", "severity": "high", "detail": "reference-only" if not raw_secret_fields else "inline values removed" if apply_safe_fixes else "inline credential fields detected"})
    local_key = next((key for key in keys if isinstance(key, dict) and key.get("provider") == "ollama"), None)
    local_route_safe = bool(local_key and _is_loopback(local_key.get("base_url", "")))
    checks.append({"id": "local_key_loopback", "worm": "Red-Team Worm", "status": "pass" if local_route_safe else "warn", "severity": "medium", "detail": str((local_key or {}).get("base_url", "not configured"))})
    checks.append({"id": "tarot_cards_present", "worm": "Scout Worm", "status": "pass" if state.get("cards") else "warn", "severity": "medium", "detail": str(len(state.get("cards", [])))})

    evidence = {
        "run_mode": "first-install" if first_install else "startup",
        "checks": checks,
        "safe_fixes": fixes,
        "policy": "Advisory red-team only; no shell commands, credential changes, account actions, or model downloads.",
    }
    review: Any = {"status": "skipped", "reason": "local model unavailable"}
    if llm_review is not None and connected and models:
        try:
            review = {"status": "complete", "output": redact_value(llm_review(redact_value(evidence)))}
        except Exception as exc:
            review = {"status": "failed", "reason": type(exc).__name__}

    blocking = [check for check in checks if check["status"] == "fail" and check["severity"] == "high"]
    verification = {
        "passed": not blocking,
        "blocking_check_ids": [check["id"] for check in blocking],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    result = redact_value({
        "status": "ready" if verification["passed"] else "degraded",
        "run_mode": "first-install" if first_install else "startup",
        "worms": list(WORM_ROLES),
        "checks": checks,
        "safe_fixes": fixes,
        "llm_review": review,
        "verification": verification,
        "safety": {
            "model_output_advisory_only": True,
            "allowlisted_repairs_only": True,
            "secrets_redacted": True,
        },
    })
    _atomic_json(Path(report_file), result)
    return result
