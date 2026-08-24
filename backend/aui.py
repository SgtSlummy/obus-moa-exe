"""Warp-inspired application UI contracts for OBus.

This module models the parts of WarpUI that are useful to OBus without copying
Warp's implementation: actions are first-class data, surfaces expose a bounded
command set, and focused views provide concise accessibility descriptions.

The contract is intentionally frontend-agnostic and secret-free. It describes
what the UI can do; it does not execute actions or contain provider credentials.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

AUI_SCHEMA_VERSION = 1
SURFACE_RANK = {"terminal": 0, "operator": 1, "ade": 2}


_ACTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "route.focus",
        "label": "Route task",
        "hint": "Focus the main OBus prompt composer",
        "section": "Navigation",
        "shortcut": "Ctrl+L",
        "surface_min": "terminal",
        "target": "route-input",
    },
    {
        "id": "route.run",
        "label": "Plan and run route",
        "hint": "Execute the current prompt through the local-first MOA",
        "section": "Execution",
        "shortcut": "Enter",
        "surface_min": "terminal",
        "target": "route-btn",
    },
    {
        "id": "plan.deliberate",
        "label": "Preview a plan",
        "hint": "Preview bounded parallel Tarot roles before enabling route deliberation",
        "section": "Execution",
        "shortcut": "Ctrl+Shift+L",
        "surface_min": "terminal",
        "target": "plan-input",
    },
    {
        "id": "route.reinput_latest",
        "label": "Re-input latest prompt",
        "hint": "Restore the last route prompt to the composer",
        "section": "Execution",
        "shortcut": None,
        "surface_min": "terminal",
        "target": "reinput-latest",
    },
    {
        "id": "route.retry_latest",
        "label": "Retry latest route",
        "hint": "Run the last route prompt again",
        "section": "Execution",
        "shortcut": None,
        "surface_min": "terminal",
        "target": "retry-latest",
    },
    {
        "id": "status.refresh",
        "label": "Refresh live state",
        "hint": "Reload dashboard, rooms, forums, and runtime state",
        "section": "Workspace",
        "shortcut": "Ctrl+R",
        "surface_min": "terminal",
        "target": "refresh-btn",
    },
    {
        "id": "runtime.warm_gpu",
        "label": "Warm GPU",
        "hint": "Keep the selected local model resident",
        "section": "Runtime",
        "shortcut": None,
        "surface_min": "terminal",
        "target": "warm-gpu",
    },
    {
        "id": "view.providers",
        "label": "Cards & Keys",
        "hint": "Review Tarot personas and Solomon's Key readiness",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "providers",
    },
    {
        "id": "view.agents",
        "label": "Agent personas",
        "hint": "Browse the 78 Tarot agent personas",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "agents",
    },
    {
        "id": "view.runtime",
        "label": "Persistent agents",
        "hint": "Open durable agent jobs and orchestration",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "runtime",
    },
    {
        "id": "view.rooms",
        "label": "Rooms",
        "hint": "Open isolated Tarot councils",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "rooms",
    },
    {
        "id": "view.receipts",
        "label": "Run receipts",
        "hint": "Inspect redacted route handoffs",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "runs",
    },
    {
        "id": "view.memory",
        "label": "Memory",
        "hint": "Search and manage bounded local/shared memory",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "memory",
    },
    {
        "id": "view.studios",
        "label": "Visual studio",
        "hint": "Open ComfyUI, graph context, and Warp companion status",
        "section": "Views",
        "shortcut": None,
        "surface_min": "operator",
        "target": "studios",
    },
    {
        "id": "view.forum",
        "label": "Chymeria forum",
        "hint": "Compare sanitized decisions across isolated rooms",
        "section": "Views",
        "shortcut": None,
        "surface_min": "ade",
        "target": "forum",
    },
    {
        "id": "view.forge",
        "label": "Arcana Forge",
        "hint": "Review bounded local tool integrations",
        "section": "Views",
        "shortcut": None,
        "surface_min": "ade",
        "target": "forge",
    },
    {
        "id": "view.hardening",
        "label": "Safety audit",
        "hint": "Inspect Tentacle Worm hardening and verification",
        "section": "Views",
        "shortcut": None,
        "surface_min": "ade",
        "target": "hardening",
    },
    {
        "id": "view.settings",
        "label": "Settings",
        "hint": "Configure surface, routing, RAG, and portable preferences",
        "section": "Views",
        "shortcut": None,
        "surface_min": "terminal",
        "target": "settings",
    },
    {
        "id": "workspace.refresh",
        "label": "Refresh workspace context",
        "hint": "Reload the configured bounded read-only workspace tree",
        "section": "Workspace",
        "shortcut": None,
        "surface_min": "terminal",
        "target": "workspace-refresh",
    },
    {
        "id": "receipt.export_latest",
        "label": "Export latest receipt",
        "hint": "Download the latest secret-safe route handoff",
        "section": "Handoffs",
        "shortcut": None,
        "surface_min": "operator",
        "target": "export-latest-receipt",
    },
)


_ACCESSIBLE_VIEWS: tuple[dict[str, Any], ...] = (
    {
        "id": "route-workbench",
        "label": "Route workbench",
        "role": "application",
        "value": "OBus route composer and live execution output",
        "help": "Enter runs the route. Shift+Enter inserts a newline. Escape returns focus here.",
        "target": "terminal-workbench",
        "surface_min": "terminal",
    },
    {
        "id": "route-output",
        "label": "Route output",
        "role": "status",
        "value": "Specialist, synthesis, verification, and aggregate stages",
        "help": "Output follows the route while Follow output is enabled.",
        "target": "route-output-panel",
        "surface_min": "terminal",
    },
    {
        "id": "key-registry",
        "label": "Solomon's Key registry",
        "role": "list",
        "value": "Provider routes and readiness states",
        "help": "Keys expose references only; credentials are never entered in OBus.",
        "target": "provider-list",
        "surface_min": "operator",
    },
    {
        "id": "rooms-council",
        "label": "Isolated rooms",
        "role": "region",
        "value": "Private Tarot council transcripts and Chymeria decisions",
        "help": "Only sanitized Chymeria packets leave a room for forum deliberation.",
        "target": "room-detail",
        "surface_min": "operator",
    },
    {
        "id": "command-palette",
        "label": "Command palette",
        "role": "dialog",
        "value": "Searchable OBus actions",
        "help": "Ctrl+K opens the palette. Arrow keys select an action. Escape closes it.",
        "target": "command-palette",
        "surface_min": "terminal",
    },
)


def _visible(item: dict[str, Any], surface: str) -> bool:
    normalized = surface if surface in SURFACE_RANK else "operator"
    return SURFACE_RANK[item.get("surface_min", "terminal")] <= SURFACE_RANK[normalized]


def build_manifest(surface: str = "operator") -> dict[str, Any]:
    """Return the public AUI contract for one workspace surface."""
    normalized = surface if surface in SURFACE_RANK else "operator"
    actions = [deepcopy(item) for item in _ACTIONS if _visible(item, normalized)]
    views = [deepcopy(item) for item in _ACCESSIBLE_VIEWS if _visible(item, normalized)]
    return {
        "schema_version": AUI_SCHEMA_VERSION,
        "model": "warp-inspired-action-accessibility",
        "surface": normalized,
        "surface_rank": SURFACE_RANK[normalized],
        "actions": actions,
        "views": views,
        "keyboard": {
            "open_palette": "Ctrl+K",
            "alternate_palette": "Ctrl+Shift+P",
            "focus_route": "Ctrl+L",
            "close_or_return_to_route": "Escape",
            "run_route": "Enter",
            "newline_in_route": "Shift+Enter",
        },
        "principles": [
            "Actions are searchable and executable from keyboard or pointer.",
            "Focus returns to the route composer after transient UI closes.",
            "Meaningful state changes are announced through a live region.",
            "Provider credentials and task secrets are outside the AUI contract.",
        ],
    }


def action_ids(surface: str = "operator") -> list[str]:
    """Return visible action identifiers for contract tests and adapters."""
    return [item["id"] for item in build_manifest(surface)["actions"]]
