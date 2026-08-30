import pytest

from backend.upstream_agent_adapters import (
    AutoAgentPlan,
    HarnessCapability,
    HarnessPlugin,
    HarnessPluginRegistry,
)


def test_harness_registry_exposes_only_enabled_capabilities_in_order():
    registry = HarnessPluginRegistry(
        [
            HarnessPlugin("zeta", (HarnessCapability("hidden"),), enabled=False),
            HarnessPlugin("alpha", (HarnessCapability("search"), HarnessCapability("fetch"))),
        ]
    )

    assert [capability.name for capability in registry.enabled_capabilities()] == ["search", "fetch"]
    assert registry.manifest() == {
        "framework": "deepseek-harness",
        "plugins": [
            {"name": "alpha", "enabled": True, "capabilities": ["search", "fetch"]},
            {"name": "zeta", "enabled": False, "capabilities": ["hidden"]},
        ],
    }


def test_harness_registry_rejects_duplicate_plugin_without_replacement():
    registry = HarnessPluginRegistry([HarnessPlugin("tools")])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(HarnessPlugin("tools"))


def test_autoagent_plan_converts_reviewable_steps_to_obus_actions():
    plan = AutoAgentPlan.from_mapping(
        {
            "title": "Research then act",
            "steps": [
                {"objective": "collect facts", "agent": "researcher", "inputs": {"topic": "obus"}},
                {"objective": "apply result", "requires_approval": True},
            ],
        }
    )

    assert plan.obus_actions() == (
        {
            "id": "upstream-1",
            "agent": "researcher",
            "objective": "collect facts",
            "inputs": {"topic": "obus"},
            "requires_approval": False,
            "framework": "autoagent",
        },
        {
            "id": "upstream-2",
            "agent": "general",
            "objective": "apply result",
            "inputs": {},
            "requires_approval": True,
            "framework": "autoagent",
        },
    )


@pytest.mark.parametrize(
    "payload",
    [{}, {"steps": "not-a-list"}, {"steps": [{"objective": "ok", "inputs": []}]}],
)
def test_autoagent_plan_rejects_invalid_payloads(payload):
    with pytest.raises(ValueError):
        AutoAgentPlan.from_mapping(payload)
