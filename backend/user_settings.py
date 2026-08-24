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

DEFAULT_USER_SETTINGS: dict[str, Any] = {
    "settings_schema_version": 1,
    "workspace_surface": "operator",
    "routing_policy": "local-first",
    "workspace_root": None,
    "rag_enabled": True,
    "auto_memory": True,
    "rag_character_budget": 2400,
    "max_parallel_agents": 5,
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
    if normalized["gpu_backend"] not in {"auto", "cpu", "cuda:0"}:
        normalized["gpu_backend"] = DEFAULT_USER_SETTINGS["gpu_backend"]
    if normalized["workspace_root"] is not None and not isinstance(normalized["workspace_root"], str):
        normalized["workspace_root"] = None
    if not 800 <= int(normalized["rag_character_budget"] or 0) <= 8000:
        normalized["rag_character_budget"] = DEFAULT_USER_SETTINGS["rag_character_budget"]
    if not 1 <= int(normalized["max_parallel_agents"] or 0) <= 20:
        normalized["max_parallel_agents"] = DEFAULT_USER_SETTINGS["max_parallel_agents"]
    for field in ("rag_enabled", "auto_memory", "warp_preprocess_enabled", "harness_enabled", "output_autoscroll"):
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
    if "rag_character_budget" in payload and not 800 <= int(payload["rag_character_budget"]) <= 8000:
        raise ValueError("rag_character_budget must be 800-8000")
    if "max_parallel_agents" in payload and not 1 <= int(payload["max_parallel_agents"]) <= 20:
        raise ValueError("max_parallel_agents must be 1-20")
    if "workspace_surface" in payload and payload["workspace_surface"] not in WORKSPACE_SURFACES:
        raise ValueError("workspace_surface must be terminal, operator, or ade")
    if "routing_policy" in payload and payload["routing_policy"] not in ROUTING_POLICIES:
        raise ValueError("routing_policy must be local-first, auto-open, or manual")
    return candidate


def export_user_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    """Return only the allowlisted, portable settings fields."""
    normalized = normalize_user_settings(settings)
    exported = {key: normalized[key] for key in USER_SETTING_FIELDS}
    if _contains_secret_shape(exported):
        raise ValueError("settings export contained secret-shaped data")
    return exported
