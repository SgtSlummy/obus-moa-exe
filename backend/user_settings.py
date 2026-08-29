"""Versioned, non-secret OBus user settings helpers.

This module deliberately contains only portable preferences. Provider credentials,
access-gate state, machine identity, and private-key material are not part of the
portable settings contract.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

WORKSPACE_SURFACES = {"terminal", "operator", "ade"}
ROUTING_POLICIES = {"local-first", "auto-open", "manual"}
AUTONOMY_LEVELS = {"conservative", "balanced", "high"}

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "settings_schema_version": 1,
    "workspace_surface": "operator",
    "routing_policy": "local-first",
    "workspace_root": None,
    "rag_enabled": True,
    "auto_memory": True,
    "rag_character_budget": 2400,
    "max_parallel_agents": 5,
    "autonomy_level": "high",
    "auto_parallelize": True,
    "shared_task_context": True,
    "context_utilization_percent": 95,
    "per_agent_context_window": 0,
    "selected_model": "gpt-oss:20b",
    "selected_deck": "auto",
    "gpu_backend": "auto",
    "warp_preprocess_enabled": False,
    "harness_enabled": True,
    "output_autoscroll": True,
}

USER_SETTING_FIELDS = frozenset(DEFAULT_USER_SETTINGS)
_SECRET_FIELD_NAMES = {
    "api_key", "apikey", "token", "access_token", "refresh_token", "password",
    "secret", "private_key", "private_key_contents", "credential", "credentials",
}


def _contains_secret_shape(value: Any, key: str | None = None) -> bool:
    if key and key.lower() in _SECRET_FIELD_NAMES:
        return True
    if isinstance(value, dict):
        return any(_contains_secret_shape(child, str(child_key)) for child_key, child in value.items())
    if isinstance(value, list):
        return any(_contains_secret_shape(child) for child in value)
    if isinstance(value, str):
        upper = value.upper()
        return "BEGIN PRIVATE KEY" in upper or "BEGIN OPENSSH PRIVATE KEY" in upper
    return False


def normalize_user_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Merge settings with safe defaults and normalize invalid portable values."""
    incoming = dict(settings or {})
    normalized = deepcopy(DEFAULT_USER_SETTINGS)
    normalized.update({key: incoming[key] for key in USER_SETTING_FIELDS if key in incoming})

    if normalized["settings_schema_version"] != 1:
        normalized["settings_schema_version"] = 1
    if normalized["workspace_surface"] not in WORKSPACE_SURFACES:
        normalized["workspace_surface"] = DEFAULT_USER_SETTINGS["workspace_surface"]
    if normalized["routing_policy"] not in ROUTING_POLICIES:
        normalized["routing_policy"] = DEFAULT_USER_SETTINGS["routing_policy"]
    if normalized["autonomy_level"] not in AUTONOMY_LEVELS:
        normalized["autonomy_level"] = DEFAULT_USER_SETTINGS["autonomy_level"]
    if normalized["gpu_backend"] not in {"auto", "cpu", "cuda:0"}:
        normalized["gpu_backend"] = DEFAULT_USER_SETTINGS["gpu_backend"]
    if normalized["workspace_root"] is not None and not isinstance(normalized["workspace_root"], str):
        normalized["workspace_root"] = None
    try:
        rag_budget = int(normalized["rag_character_budget"] or 0)
    except (TypeError, ValueError):
        rag_budget = 0
    if not 800 <= rag_budget <= 8000:
        normalized["rag_character_budget"] = DEFAULT_USER_SETTINGS["rag_character_budget"]
    try:
        max_parallel = int(normalized["max_parallel_agents"] or 0)
    except (TypeError, ValueError):
        max_parallel = 0
    if not 1 <= max_parallel <= 20:
        normalized["max_parallel_agents"] = DEFAULT_USER_SETTINGS["max_parallel_agents"]
    try:
        utilization = int(normalized["context_utilization_percent"] or 0)
    except (TypeError, ValueError):
        utilization = 0
    if not 50 <= utilization <= 95:
        normalized["context_utilization_percent"] = DEFAULT_USER_SETTINGS["context_utilization_percent"]
    try:
        agent_context = int(normalized["per_agent_context_window"] or 0)
    except (TypeError, ValueError):
        agent_context = -1
    if agent_context != 0 and not 2048 <= agent_context <= 2_000_000:
        normalized["per_agent_context_window"] = DEFAULT_USER_SETTINGS["per_agent_context_window"]
    for field in ("rag_enabled", "auto_memory", "auto_parallelize", "shared_task_context", "warp_preprocess_enabled", "harness_enabled", "output_autoscroll"):
        if not isinstance(normalized[field], bool):
            normalized[field] = DEFAULT_USER_SETTINGS[field]
    for field in ("selected_model", "selected_deck"):
        if not isinstance(normalized[field], str):
            normalized[field] = DEFAULT_USER_SETTINGS[field]
    return normalized


def validate_import_payload(payload: Any) -> dict[str, Any]:
    """Validate and normalize a portable settings document before persistence."""
    if not isinstance(payload, dict):
        raise ValueError("settings import must be a JSON object")
    unknown = set(payload) - USER_SETTING_FIELDS
    if unknown:
        raise ValueError(f"unsupported settings fields: {', '.join(sorted(unknown))}")
    if _contains_secret_shape(payload):
        raise ValueError("portable settings cannot contain credentials or private key material")
    if "settings_schema_version" in payload and payload["settings_schema_version"] != 1:
        raise ValueError("unsupported settings_schema_version")
    candidate = normalize_user_settings(payload)
    try:
        if "rag_character_budget" in payload and not 800 <= int(payload["rag_character_budget"]) <= 8000:
            raise ValueError("rag_character_budget must be 800-8000")
        if "max_parallel_agents" in payload and not 1 <= int(payload["max_parallel_agents"]) <= 20:
            raise ValueError("max_parallel_agents must be 1-20")
        if "context_utilization_percent" in payload and not 50 <= int(payload["context_utilization_percent"]) <= 95:
            raise ValueError("context_utilization_percent must be 50-95")
        if "per_agent_context_window" in payload and int(payload["per_agent_context_window"]) != 0 and not 2048 <= int(payload["per_agent_context_window"]) <= 2_000_000:
            raise ValueError("per_agent_context_window must be 0 or 2048-2000000")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith((
            "rag_character_budget", "max_parallel_agents", "context_utilization_percent", "per_agent_context_window",
        )):
            raise
        raise ValueError("numeric settings must be valid integers") from exc
    if "workspace_surface" in payload and payload["workspace_surface"] not in WORKSPACE_SURFACES:
        raise ValueError("workspace_surface must be terminal, operator, or ade")
    if "routing_policy" in payload and payload["routing_policy"] not in ROUTING_POLICIES:
        raise ValueError("routing_policy must be local-first, auto-open, or manual")
    if "autonomy_level" in payload and payload["autonomy_level"] not in AUTONOMY_LEVELS:
        raise ValueError("autonomy_level must be conservative, balanced, or high")
    return candidate


def export_user_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Return only the allowlisted, portable settings fields."""
    normalized = normalize_user_settings(settings)
    exported = {key: normalized[key] for key in USER_SETTING_FIELDS}
    if _contains_secret_shape(exported):
        raise ValueError("settings export contained secret-shaped data")
    return exported
