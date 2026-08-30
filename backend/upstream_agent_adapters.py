"""Small, dependency-free adapters for external agent-framework concepts.

The module deliberately imports neither upstream project. It captures the
portable contracts OBus can use: named, enableable capabilities from
DeepSeek Harness and deterministic command plans from AutoAgent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class UpstreamFramework(str, Enum):
    DEEPSEEK_HARNESS = "deepseek-harness"
    AUTOAGENT = "autoagent"


@dataclass(frozen=True)
class HarnessCapability:
    """A declarative DeepSeek-Harness-style plugin capability."""

    name: str
    description: str = ""
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("capability name must be non-empty")


@dataclass(frozen=True)
class HarnessPlugin:
    """A local plugin descriptor; no foreign code is loaded or executed."""

    name: str
    capabilities: tuple[HarnessCapability, ...] = ()
    enabled: bool = True
    configuration: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("plugin name must be non-empty")
        names = [capability.name for capability in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("plugin capability names must be unique")


class HarnessPluginRegistry:
    """Registry with explicit replacement semantics and stable snapshots."""

    def __init__(self, plugins: Iterable[HarnessPlugin] = ()) -> None:
        self._plugins: dict[str, HarnessPlugin] = {}
        for plugin in plugins:
            self.register(plugin)

    def register(self, plugin: HarnessPlugin, *, replace: bool = False) -> None:
        if plugin.name in self._plugins and not replace:
            raise ValueError(f"plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin

    def get(self, name: str) -> HarnessPlugin | None:
        return self._plugins.get(name)

    def enabled_capabilities(self) -> tuple[HarnessCapability, ...]:
        return tuple(
            capability
            for name in sorted(self._plugins)
            for capability in self._plugins[name].capabilities
            if self._plugins[name].enabled
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "framework": UpstreamFramework.DEEPSEEK_HARNESS.value,
            "plugins": [
                {
                    "name": plugin.name,
                    "enabled": plugin.enabled,
                    "capabilities": [capability.name for capability in plugin.capabilities],
                }
                for plugin in (self._plugins[name] for name in sorted(self._plugins))
            ],
        }


@dataclass(frozen=True)
class AutoAgentStep:
    """A serializable, reviewable unit of work inspired by AutoAgent tasks."""

    objective: str
    agent: str = "general"
    inputs: Mapping[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    def __post_init__(self) -> None:
        if not self.objective or not self.objective.strip():
            raise ValueError("step objective must be non-empty")
        if not self.agent or not self.agent.strip():
            raise ValueError("step agent must be non-empty")

    def as_obus_action(self, position: int) -> dict[str, Any]:
        """Return a neutral action payload consumable by OBus orchestration."""
        return {
            "id": f"upstream-{position}",
            "agent": self.agent,
            "objective": self.objective,
            "inputs": dict(self.inputs),
            "requires_approval": self.requires_approval,
            "framework": UpstreamFramework.AUTOAGENT.value,
        }


@dataclass(frozen=True)
class AutoAgentPlan:
    """Validated plan that keeps approval boundaries explicit."""

    steps: tuple[AutoAgentStep, ...]
    title: str = "AutoAgent plan"

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("plan must include at least one step")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AutoAgentPlan":
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("plan steps must be a list")
        steps: list[AutoAgentStep] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, Mapping):
                raise ValueError("each plan step must be an object")
            inputs = raw_step.get("inputs", {})
            if not isinstance(inputs, Mapping):
                raise ValueError("step inputs must be an object")
            steps.append(
                AutoAgentStep(
                    objective=str(raw_step.get("objective", "")),
                    agent=str(raw_step.get("agent", "general")),
                    inputs=dict(inputs),
                    requires_approval=bool(raw_step.get("requires_approval", False)),
                )
            )
        return cls(steps=tuple(steps), title=str(payload.get("title", "AutoAgent plan")))

    def obus_actions(self) -> tuple[dict[str, Any], ...]:
        return tuple(step.as_obus_action(index) for index, step in enumerate(self.steps, start=1))

    def manifest(self) -> dict[str, Any]:
        return {
            "framework": UpstreamFramework.AUTOAGENT.value,
            "title": self.title,
            "actions": list(self.obus_actions()),
        }
