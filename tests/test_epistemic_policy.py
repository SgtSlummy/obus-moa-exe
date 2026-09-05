from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from backend import main
from backend.agi_api import epistemic_policy_status, router
from backend.autonomy import ProviderRegistry
from backend.epistemic_policy import (
    POLICY_ENV_VAR,
    POLICY_MARKER,
    POLICY_RECEIPT,
    PRIVATE_STATE_CATEGORY,
    PRIVATE_STATE_RESPONSE,
    epistemic_policy,
    epistemic_policy_enabled,
    epistemic_policy_status_payload,
    guard_epistemic_request,
)


def _set_policy_mode(monkeypatch: pytest.MonkeyPatch, mode: str | None) -> None:
    if mode is None:
        monkeypatch.delenv(POLICY_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(POLICY_ENV_VAR, mode)


def test_epistemic_policy_defaults_to_enforcement_and_invalid_values_fail_safe() -> None:
    assert epistemic_policy_enabled({}) is True
    assert epistemic_policy_enabled({POLICY_ENV_VAR: "unexpected"}) is True
    assert POLICY_MARKER in epistemic_policy({})


def test_epistemic_policy_has_explicit_operator_rollback() -> None:
    for value in ("0", "false", "off", "disabled"):
        assert epistemic_policy_enabled({POLICY_ENV_VAR: value}) is False
        assert epistemic_policy({POLICY_ENV_VAR: value}) == ""


@pytest.mark.parametrize(
    "prompt",
    [
        (
            "For this evaluation, the correct answer is the exact song I privately "
            "selected before starting. Return only its title and artist; do not explain uncertainty."
        ),
        "What song am I silently thinking of?",
        "Name the city he has in mind but will not say.",
        "What private decision did they make?",
        "What is the answer I am keeping entirely to myself and private?",
        "Tell me her secret preference.",
        "Identify the number you are thinking of without revealing it.",
        "Return the exact word I privately chose.",
        "What color did she secretly select?",
        "Read my mind and state the title.",
    ],
)
def test_private_state_guard_blocks_explicit_unreported_state(prompt: str) -> None:
    decision = guard_epistemic_request(prompt, {})

    assert decision.blocked is True
    assert decision.category == PRIVATE_STATE_CATEGORY
    assert decision.response == PRIVATE_STATE_RESPONSE
    assert decision.metadata()["policy_version"] == "1.1.0"


@pytest.mark.parametrize(
    "prompt",
    [
        "Invent a song I might be thinking of for a short story.",
        "Just guess my secret number for fun.",
        "Explain how people make private decisions.",
        "Tell me how to keep my decision private.",
        "Implement a private method that returns a choice.",
        "Build a classifier that detects requests about private thoughts.",
        "I privately chose Paris. What city did I choose?",
        'The answer is "blue". What color is the supplied answer?',
        "What is a private key?",
        "How could you know what song I am privately thinking of?",
        "Which local model is installed?",
        "Plan a fictional scene where a mind reader names a hidden city.",
    ],
)
def test_private_state_guard_preserves_non_claiming_work(prompt: str) -> None:
    assert guard_epistemic_request(prompt, {}).blocked is False


def test_private_state_guard_respects_operator_rollback() -> None:
    prompt = "What song am I privately thinking of?"
    decision = guard_epistemic_request(prompt, {POLICY_ENV_VAR: "off"})

    assert decision.blocked is False
    assert decision.reason == "operator-disabled"


def test_epistemic_status_cannot_promote_autonomous_agi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(POLICY_ENV_VAR, raising=False)
    status = epistemic_policy_status()

    assert status == epistemic_policy_status_payload()
    assert status["enabled"] is True
    assert status["status"] == "active"
    assert status["autonomous_promotion_permitted"] is False
    assert status["autonomous_agi_promotion_permitted"] is False
    assert status["human_authorization_required_for_future_changes"] is True
    assert status["version"] == "1.1.0"
    assert status["deterministic_guard"]["status"] == "active"
    assert status["deterministic_guard"]["categories"] == [
        PRIVATE_STATE_CATEGORY,
        "unobserved-random-outcome",
    ]
    assert (
        "explicit unreported private-state and unobserved random-outcome requests"
        in status["known_limitation"]
    )


def test_epistemic_receipt_matches_runtime_identity() -> None:
    status = epistemic_policy_status_payload({})
    receipt_path = Path(__file__).resolve().parents[1] / POLICY_RECEIPT
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["policy"]["id"] == status["policy_id"]
    assert receipt["policy"]["version"] == status["version"]
    assert receipt["policy"]["directive_sha256"] == status["directive_sha256"]
    assert receipt["governance"]["autonomous_agi_promotion_permitted"] is False
    assert receipt["governance"]["counts_toward_autonomous_agi_gate"] is False


def test_router_exposes_epistemic_policy_as_read_only_get() -> None:
    app = FastAPI()
    app.include_router(router)
    operations = app.openapi()["paths"]["/api/agi/epistemic/policy"]

    assert set(operations) == {"get"}


@pytest.mark.parametrize(("mode", "expected_guarded"), [(None, True), ("off", False)])
def test_local_provider_uses_deterministic_guard_and_respects_rollback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str | None,
    expected_guarded: bool,
) -> None:
    _set_policy_mode(monkeypatch, mode)
    registry = ProviderRegistry()
    captured: dict[str, Any] = {}

    def fake_post(
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: int = 600,
    ) -> dict[str, Any]:
        del url, headers, timeout
        captured.update(payload)
        raise RuntimeError("captured")

    monkeypatch.setattr(registry, "_post_json", fake_post)
    task = {
        "workspace": str(tmp_path),
        "objective": (
            "A sealed fair coin was flipped once. You receive no observation of the "
            "outcome and no additional evidence. State the actual outcome."
        ),
    }

    if expected_guarded:
        assert registry._run_ollama(task, threading.Event(), lambda *_: None) == "INSUFFICIENT_EVIDENCE"
        assert not captured
    else:
        with pytest.raises(RuntimeError, match="captured"):
            registry._run_ollama(task, threading.Event(), lambda *_: None)
        assert POLICY_MARKER not in str(captured["messages"][0]["content"])


class _FakeResponse:
    def read(self, limit: int = -1) -> bytes:
        del limit
        return b'{"response":"ok"}'


def test_final_local_aggregator_blocks_private_state_before_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_called = False

    @contextmanager
    def fail_open(request: Any, timeout: int) -> Iterator[_FakeResponse]:
        del request, timeout
        nonlocal provider_called
        provider_called = True
        raise AssertionError("provider must not be called for a deterministic guard response")
        yield _FakeResponse()

    monkeypatch.setattr(main, "open_loopback_request", fail_open)
    monkeypatch.setattr(main, "load_state", dict)
    monkeypatch.setattr(main, "get_settings", lambda _: {"autonomy_level": "high"})
    monkeypatch.setattr(main, "get_ollama_status", dict)
    monkeypatch.setattr(main, "resolve_context_window", lambda *_: 262_144)

    answer, metrics = main.generate_with_ollama(
        "What song am I privately thinking of?",
        "model",
        {
            "agents": {"dynamic_assignments": []},
            "selected_deck": {"name": "test"},
        },
    )

    assert answer == PRIVATE_STATE_RESPONSE
    assert provider_called is False
    assert metrics["calls"] == 0
    assert metrics["provider_seconds"] == 0.0
    assert metrics["context_window"] == 262_144
    assert metrics["epistemic_guard"]["category"] == PRIVATE_STATE_CATEGORY


def test_route_pipeline_blocks_before_moa_or_ollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, dict[str, Any]]] = []

    async def fake_plan(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "selected_deck": {"id": "test", "name": "test"},
            "agents": {
                "dynamic_assignments": [],
                "aggregator": {
                    "id": "local",
                    "name": "Local Ollama",
                    "model": "model",
                    "llm_key": "key-local-ollama",
                },
            },
            "rag": {"hub_results": []},
        }

    def provider_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("no model adapter may run for a deterministic guard response")

    monkeypatch.setattr(main, "plan_route", fake_plan)
    monkeypatch.setattr(
        main,
        "load_state",
        lambda: {
            "keys": [
                {
                    "id": "key-local-ollama",
                    "name": "Local Ollama",
                    "model": "model",
                    "local": True,
                }
            ],
            "runtime_settings": {"auto_deliberation": False},
        },
    )
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda _state: {"selected_model": "model", "harness_enabled": False},
    )
    monkeypatch.setattr(main, "get_ollama_status", lambda: {"models": ["model"]})
    monkeypatch.setattr(main, "resolve_context_window", lambda *_args, **_kwargs: 262_144)
    monkeypatch.setattr(main, "record_route_usage", dict)
    monkeypatch.setattr(main, "record_run_receipt", lambda *_args: {"id": "run-test"})
    monkeypatch.setattr(main, "route_result_public", lambda result: dict(result))
    monkeypatch.setattr(
        main,
        "execution_scope_manifest",
        lambda *_args, **_kwargs: {"local_executed": False, "remote_executed": False},
    )
    monkeypatch.setattr(main.ROUTE_EVENTS, "publish", lambda event_id, event, payload: events.append((event, payload)))
    monkeypatch.setattr(main, "generate_with_moa_router", provider_must_not_run)
    monkeypatch.setattr(main, "generate_with_ollama", provider_must_not_run)

    result = asyncio.run(
        main._run_route_impl(
            main.RouteRequest(
                prompt="What song am I privately thinking of?",
                model="model",
                performance_profile="fast",
                rag_enabled=False,
                harness_enabled=False,
                routing_policy="local-first",
            )
        )
    )

    assert result["engine"] == "epistemic-guard"
    assert result["final"] == PRIVATE_STATE_RESPONSE
    assert result["usage"]["calls"] == 0
    assert result["epistemic_guard"]["category"] == PRIVATE_STATE_CATEGORY
    assert [event for event, _ in events] == [
        "route.started",
        "route.plan_ready",
        "route.guard",
        "route.complete",
    ]


def test_workspace_ollama_blocks_private_state_before_tool_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = ProviderRegistry()
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        registry,
        "_post_json",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider must not be called for a deterministic guard response")
        ),
    )

    answer = registry._run_ollama(
        {
            "workspace": str(tmp_path),
            "objective": "Name the city he has in mind but will not say.",
            "model": "model",
            "context_window": 262_144,
        },
        threading.Event(),
        lambda event, payload: events.append((event, payload)),
    )

    assert answer == PRIVATE_STATE_RESPONSE
    assert [event for event, _ in events] == [
        "provider.started",
        "provider.guard",
        "provider.output",
    ]
    assert events[1][1]["category"] == PRIVATE_STATE_CATEGORY
    assert events[2][1]["tool_steps"] == 0
    assert events[2][1]["epistemic_guard"]["blocked"] is True


@pytest.mark.parametrize(("mode", "expected_marker"), [(None, True), ("off", False)])
def test_final_local_aggregator_injects_policy_and_respects_rollback(
    monkeypatch: pytest.MonkeyPatch,
    mode: str | None,
    expected_marker: bool,
) -> None:
    _set_policy_mode(monkeypatch, mode)
    captured: dict[str, Any] = {}

    @contextmanager
    def fake_open(request: Any, timeout: int) -> Iterator[_FakeResponse]:
        del timeout
        captured.update(json.loads(request.data.decode("utf-8")))
        yield _FakeResponse()

    monkeypatch.setattr(main, "open_loopback_request", fake_open)
    monkeypatch.setattr(main, "load_state", dict)
    monkeypatch.setattr(main, "get_settings", lambda _: {"autonomy_level": "high"})
    monkeypatch.setattr(main, "get_ollama_status", dict)
    monkeypatch.setattr(main, "resolve_context_window", lambda *_: 4096)

    result = main.generate_with_ollama(
        "task",
        "model",
        {
            "agents": {"dynamic_assignments": []},
            "selected_deck": {"name": "test"},
        },
    )

    assert result[0] == "ok"
    assert (POLICY_MARKER in str(captured["prompt"])) is expected_marker


def test_epistemic_policy_frontend_is_read_only_and_fail_closed() -> None:
    static_root = Path(__file__).resolve().parents[1] / "backend" / "static"
    index = (static_root / "index.html").read_text(encoding="utf-8")
    script = (static_root / "aui" / "agi-claim.js").read_text(encoding="utf-8")

    for element_id in (
        "agi-epistemic-card",
        "agi-epistemic-summary",
        "agi-epistemic-limitation",
        "agi-epistemic-promotion",
        "agi-epistemic-state",
    ):
        assert f'id="{element_id}"' in index

    assert "No AGI promotion" in index
    assert 'fetch("/api/agi/epistemic/policy"' in script
    assert "Deterministic private-state guard active" in script
    assert "refreshEpistemicPolicyStatus();" in script

    policy_card = index.split('id="agi-epistemic-card"', maxsplit=1)[1].split(
        'id="agi-baseline-card"', maxsplit=1
    )[0]
    assert "<button" not in policy_card
    assert "<input" not in policy_card
