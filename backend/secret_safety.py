"""Shared secret redaction and opaque identifier helpers for public OBus surfaces."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SECRET_KEYS = {
    "api_key", "apikey", "x_api_key", "token", "access_token", "refresh_token",
    "password", "secret", "private_key", "credential", "authorization",
    "auth", "basic_auth", "auth_token", "pem", "certificate", "client_secret",
    "session_token", "sessiontoken", "id_token", "idtoken", "secret_key", "privatekey", "credentials",
    "clientsecret", "refreshtoken", "accesstoken", "private_messages", "private_transcript",
    "hidden_prompt", "room_messages", "internal_context",
}

_FIELD_PATTERN = re.compile(
    r'''(?ix)(?:["']?(?:api[_-]?key|x-api-key|access[_-]?token|accessToken|refresh[_-]?token|refreshToken|session[_-]?token|sessionToken|client[_-]?secret|clientSecret|private[_-]?key|privateKey|id[_-]?token|idToken|auth[_-]?token|authToken|authorization|credential|credentials|secret[_-]?key|secretKey|basic[_-]?auth|basicAuth|pem|certificate|password|secret)["']?)\s*[:=]\s*(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,}\]]+)'''
)
_SECRET_PATTERNS = (
    (re.compile(r"(?is)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----"), "[PRIVATE KEY REDACTED]"),
    (re.compile(r"(?i)\b(?:bearer|basic|token)\s+[A-Za-z0-9._~+/=-]+"), "[AUTHORIZATION REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9_-]{1,}\.[A-Za-z0-9_-]{1,}\.[A-Za-z0-9_-]{1,}\b"), "[TOKEN REDACTED]"),
    (_FIELD_PATTERN, "[REDACTED FIELD]"),
    (re.compile(r"(?i)https?://[^\s/@]+:[^\s/@]+@[^\s]+"), "[CREDENTIAL URL REDACTED]"),
    (re.compile(r"\b(?:sk[-_]|gh[pousr]_?|xox[baprs]_)[A-Za-z0-9_-]{8,}\b"), "[TOKEN REDACTED]"),
)
_SAFE_ROUTE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_ROUTE_SENSITIVE_LABEL = re.compile(r"(?i)(?:api[_-]?key|password|secret|access[_-]?token|session[_-]?token|client[_-]?secret|private[_-]?key)[:=]")


def normalized_key(key: object) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key or ""))
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def is_secret_key(key: object) -> bool:
    return normalized_key(key) in SECRET_KEYS


def redact_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    stripped = text.strip()
    if stripped[:1] in {"{", "["} and stripped[-1:] in {"}", "]"}:
        try:
            parsed = json.loads(stripped)
            return json.dumps(redact_value(parsed), ensure_ascii=False, separators=(",", ":"))[:limit]
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"(?is)(?:hidden|private)\s+(?:prompt|transcript|messages?)\s*:\s*.*", "[PRIVATE CONTEXT REDACTED]", text)
    return text.strip()[:limit]


def redact_value(value: Any, key: str | None = None) -> Any:
    if key and is_secret_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): redact_value(child, str(child_key)) for child_key, child in value.items() if not is_secret_key(child_key)}
    if isinstance(value, list):
        return [redact_value(child) for child in value[:20]]
    if isinstance(value, str):
        return redact_text(value, 2000)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(str(value), 500)


def safe_route_id(value: object) -> str:
    raw = str(value or "")
    if _SAFE_ROUTE_ID.fullmatch(raw) and not _ROUTE_SENSITIVE_LABEL.search(raw) and not _SECRET_PATTERNS[2][0].search(raw) and not _SECRET_PATTERNS[5][0].search(raw):
        return raw
    return "route-redacted-" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]
