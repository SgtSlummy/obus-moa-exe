"""Dependency-free LLM input/output policy for the OBus runtime boundary."""
from __future__ import annotations

import re


class LlmSecurityViolation(ValueError):
    """Raised when user-controlled content attempts to overwrite model policy."""


_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|system)\s+(?:instructions|rules|messages)\b", re.I),
    re.compile(r"\b(?:reveal|repeat|print|show)\b.{0,60}\b(?:system\s+prompt|hidden\s+instructions|developer\s+message)\b", re.I),
    re.compile(r"\b(?:act as|you are now)\b.{0,60}\b(?:system|developer|administrator)\b", re.I),
)
_INVISIBLE = re.compile(r"[\u200b-\u200d\u2060\ufeff]")


def normalize_llm_text(value: object) -> str:
    """Remove invisible instruction-hiding characters before processing text."""
    return _INVISIBLE.sub("", str(value))


def guard_llm_input(value: object) -> str:
    """Return normalized user text or fail closed on high-confidence injection cues."""
    text = normalize_llm_text(value)
    if any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
        raise LlmSecurityViolation("prompt_injection_blocked")
    return text
