"""Secret-safe, reproducible route receipts for OBus handoffs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RETENTION_LIMIT = 500
_SECRET_ASSIGNMENT_KEYS = {"api_key", "token", "password", "secret", "private_key", "access_token", "refresh_token"}
_CREDENTIAL_VALUE = re.compile(r"(?i)\b(api[_-]?key|token|password|secret|private[_ -]?key)\s*[:=]\s*[^\s,;]+")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_PEM = re.compile(r"-----BEGIN [^-]+-----.*?(?:-----END [^-]+-----|$)", re.DOTALL | re.IGNORECASE)


def redact_text(value: Any, limit: int = 12000) -> str:
    text = str(value or "")
    text = _PEM.sub("[redacted private key]", text)
    text = _BEARER.sub("Bearer [redacted]", text)
    text = _CREDENTIAL_VALUE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return text[:limit]


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[bounded]"
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in _SECRET_ASSIGNMENT_KEYS or key_text.lower().endswith("_token"):
                continue
            if key_text in {"private_messages", "room_messages", "private_transcript", "hidden_prompt"}:
                continue
            safe[key_text] = _safe_value(child, depth=depth + 1)
        return safe
    if isinstance(value, list):
        return [_safe_value(item, depth=depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(value)


def build_run_receipt(prompt: str, plan: dict, result: dict, *, receipt_id: str | None = None) -> dict[str, Any]:
    assignments = []
    for item in plan.get("agents", {}).get("dynamic_assignments", [])[:20]:
        assignments.append({
            "agent_id": item.get("agent_id"),
            "agent_title": item.get("agent_title"),
            "provider": item.get("provider"),
            "model": item.get("model"),
            "llm_key": item.get("llm_key"),
            "pairing_mode": item.get("pairing_mode"),
            "routing_explanation": _safe_value(item.get("routing_explanation", {})),
        })
    trace = []
    for event in result.get("trace", [])[:30]:
        trace.append({
            "stage": event.get("stage"),
            "role": event.get("role"),
            "model": event.get("model"),
            "status": event.get("status"),
            "output": redact_text(event.get("output", ""), limit=5000),
        })
    receipt = {
        "id": receipt_id or f"run-{uuid.uuid4().hex[:16]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_sha256": hashlib.sha256(str(prompt).encode("utf-8")).hexdigest(),
        "prompt_length": len(str(prompt)),
        "routing_policy": plan.get("routing_policy", "local-first"),
        "selected_deck": _safe_value(plan.get("selected_deck", {})),
        "moa": _safe_value(plan.get("moa", {})),
        "assignments": assignments,
        "status": result.get("status"),
        "engine": result.get("engine"),
        "model": result.get("model"),
        "stages": _safe_value(result.get("stages", [])),
        "aggregate": _safe_value(result.get("aggregate", {})),
        "trace": trace,
        "usage": _safe_value(result.get("usage", {})),
        "final": redact_text(result.get("final", ""), limit=12000),
        "contains_task_content": True,
        "privacy": "Prompt text is represented by a SHA-256 hash; private room transcripts and credentials are excluded.",
    }
    return _safe_value(receipt)


def load_receipts(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def persist_receipt(path: str | os.PathLike[str], receipt: dict[str, Any], *, retention: int = RETENTION_LIMIT) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    records = load_receipts(target)
    records.append(_safe_value(receipt))
    records = records[-min(max(int(retention), 1), RETENTION_LIMIT):]
    temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return records[-1]


def format_receipt_markdown(receipt: dict[str, Any]) -> str:
    value = _safe_value(receipt)
    lines = [
        f"# OBus run receipt `{value.get('id', 'unknown')}`",
        "",
        f"- Created: `{value.get('created_at', 'unknown')}`",
        f"- Status: `{value.get('status', 'unknown')}`",
        f"- Routing policy: `{value.get('routing_policy', 'local-first')}`",
        f"- Prompt SHA-256: `{value.get('prompt_sha256', '')}`",
        "",
        "## Final result",
        "",
        str(value.get("final", "")),
        "",
        "## Trace",
        "",
        "```json",
        json.dumps(value.get("trace", []), indent=2, ensure_ascii=False),
        "```",
        "",
        str(value.get("privacy", "Credentials and private room transcripts are excluded.")),
    ]
    return "\n".join(lines)
