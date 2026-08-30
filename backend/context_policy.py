"""Context allocation and autonomy policy for local OBus agents."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

DEFAULT_CONTEXT_WINDOW = 131_072
MIN_CONTEXT_WINDOW = 2_048
MAX_CONTEXT_WINDOW = 2_000_000


def resolve_context_window(
    model: str,
    ollama_status: dict[str, Any] | None,
    settings: dict[str, Any] | None,
    *,
    key_limit: int | None = None,
) -> int:
    """Return a bounded per-request context window supported by the active model."""
    status = ollama_status or {}
    preferences = settings or {}
    override = int(preferences.get("per_agent_context_window") or 0)
    detected_candidates = [
        int((status.get("runtime_contexts") or {}).get(model) or 0),
        int((status.get("model_contexts") or {}).get(model) or 0),
    ]
    detected = max(detected_candidates) or int(key_limit or DEFAULT_CONTEXT_WINDOW)
    ceiling = min(value for value in (detected, key_limit or detected, MAX_CONTEXT_WINDOW) if value > 0)
    if override > 0:
        return max(MIN_CONTEXT_WINDOW, min(override, ceiling))
    utilization = min(95, max(50, int(preferences.get("context_utilization_percent") or 95)))
    return max(MIN_CONTEXT_WINDOW, int(ceiling * utilization / 100))


def bounded_agent_context(
    history: Iterable[dict[str, Any]],
    shared_findings: Iterable[dict[str, Any]],
    context_tokens: int,
) -> tuple[str, str]:
    """Build independent private-history and shared-ledger slices for one agent."""
    character_budget = max(4_000, int(context_tokens) * 3)
    private_budget = int(character_budget * 0.55)
    shared_budget = int(character_budget * 0.25)

    private_parts: list[str] = []
    used = 0
    for item in reversed(list(history)):
        text = f"Step {item.get('step')}: {item.get('output', '')}".strip()
        if not text or used + len(text) > private_budget:
            continue
        private_parts.append(text)
        used += len(text)

    shared_parts: list[str] = []
    used = 0
    for item in reversed(list(shared_findings)):
        # Task ledgers are shared state, so they may contain coordination
        # metadata but never another agent's output or transcript.
        text = f"{item.get('agent_name', 'Agent')}: completed step {item.get('step', '?')}".strip()
        if not text or used + len(text) > shared_budget:
            continue
        shared_parts.append(text)
        used += len(text)

    return "\n".join(reversed(private_parts)) or "None", "\n".join(reversed(shared_parts)) or "None"


def autonomy_directive(level: str) -> str:
    """Describe when an agent should act versus request human input."""
    if str(level).lower() == "conservative":
        return "Ask before ambiguous, external, destructive, or irreversible actions."
    if str(level).lower() == "balanced":
        return "Inspect first and act on reversible local work; ask only when risk or intent is materially ambiguous."
    return (
        "Work autonomously: inspect available state, infer reasonable defaults, split independent work in parallel, "
        "execute reversible local actions, verify results, and continue through recoverable failures. Ask only when "
        "credentials, external authority, destructive or irreversible effects, or a genuinely outcome-changing choice is required."
    )
