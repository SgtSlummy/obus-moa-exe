"""Strict game provider fixtures. No real credentials, network or model inference."""
from __future__ import annotations

import copy
import io
import json
import math
import threading
import time

import pytest

from backend import game_providers as providers


@pytest.fixture(autouse=True)
def no_live_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Provider fixture attempted a real connection")
    monkeypatch.setattr(providers.http.client, "HTTPConnection", forbidden)
    monkeypatch.setattr(providers.http.client, "HTTPSConnection", forbidden)
    monkeypatch.setenv("OBUS_TEST_PROVIDER_KEY", "fixture-secret-never-real")


def local_key():
    return {"id": "local", "provider": "ollama", "model": "campaign:fixture", "base_url": providers.LOCAL_BASE, "connected": True, "verified": True}


def free_key():
    key = {"id": "free", "provider": "openrouter", "model": "meta-llama/llama-3.2-3b-instruct:free", "base_url": providers.FREE_BASE,
           "connected": True, "verified": True, "env_var": "OBUS_TEST_PROVIDER_KEY"}
    key["game_free_pin"] = {name: key[name] for name in ("id", "provider", "model", "base_url")}
    key["game_free_pin"].update(zero_charge=True, no_fallback=True, no_tools=True, downstream_provider="deepinfra", downstream_provider_name="DeepInfra")
    return key


LOCAL_METADATA = {"details": {"format": "gguf"}, "model_info": {"general.architecture": "qwen3"}, "capabilities": ["completion", "tools"]}


def local_response():
    return {"model": "campaign:fixture", "message": {"role": "assistant", "content": "The harbor is quiet."}, "done": True, "done_reason": "stop", "eval_count": 7}


def free_response():
    return {"id": "gen-fixture", "object": "chat.completion", "model": free_key()["model"], "provider": "DeepInfra",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "The harbor is quiet."}}],
            "usage": {"completion_tokens": 7, "prompt_tokens": 5, "total_tokens": 12, "cost": 0, "is_byok": False}}


def transport_fixture(monkeypatch, response=None, metadata=None):
    calls = []
    def request(endpoint, payload, headers, deadline):
        assert time.monotonic() < deadline
        calls.append((endpoint, copy.deepcopy(payload), headers.copy(), deadline))
        if endpoint.endswith("/api/show"):
            return copy.deepcopy(LOCAL_METADATA if metadata is None else metadata)
        return copy.deepcopy(free_response() if response is None else response)
    monkeypatch.setattr(providers, "_request_json", request)
    return calls


def test_free_route_enforces_pinned_single_destination_price_tools_and_budget(monkeypatch):
    calls = transport_fixture(monkeypatch)
    result = providers.complete_free(free_key(), "Authorized scene facts only.", 48)
    assert result["provider"] == "DeepInfra" and result["gateway"] == "openrouter"
    assert result["model"] == free_key()["model"] and result["cost"] == "zero"
    assert result["completion_tokens"] == 7 and result["response_id"] == "gen-fixture"
    assert len(calls) == 1
    endpoint, request, headers, deadline = calls[0]
    assert endpoint == "https://openrouter.ai/api/v1/chat/completions"
    assert headers == {"Authorization": "Bearer fixture-secret-never-real"}
    assert request["max_tokens"] == 48 and request["model"] == free_key()["model"]
    assert request["tool_choice"] == "none" and request["parallel_tool_calls"] is False
    assert request["provider"] == {"order": ["deepinfra"], "only": ["deepinfra"], "allow_fallbacks": False, "require_parameters": True,
                                   "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0}}
    assert not {"tools", "functions", "models", "plugins", "route", "trace"}.intersection(request)
    assert "fixture-secret" not in json.dumps(result)


@pytest.mark.parametrize("change", [
    {"provider": "groq", "base_url": "https://api.groq.com/openai/v1"},
    {"provider": "codex"}, {"provider": "omniroute"},
    {"base_url": "http://openrouter.ai/api/v1"}, {"base_url": "https://openrouter.ai.evil.invalid/api/v1"},
    {"base_url": "https://openrouter.ai/api/v1/"}, {"base_url": "https://openrouter.ai/api/v1?fallback=paid"},
    {"model": "openrouter/free"}, {"model": "openrouter/auto:free"}, {"model": "vendor/model"},
    {"model": "vendor/model:online"}, {"model": "vendor/compound:free"},
    {"verified": 1}, {"connected": "true"}, {"game_free_pin": None},
])
def test_unapproved_unknown_cost_router_and_paid_routes_never_dispatch(monkeypatch, change):
    calls = transport_fixture(monkeypatch)
    key = free_key()
    key.update(change)
    with pytest.raises(providers.GameProviderError):
        providers.complete_free(key, "private fixture", 32)
    assert calls == []


@pytest.mark.parametrize("change", [
    {"zero_charge": "true"}, {"no_fallback": 1}, {"no_tools": False}, {"id": "other"},
    {"model": "vendor/different:free"}, {"provider": "groq"}, {"base_url": "https://proxy.invalid"},
    {"downstream_provider": "auto"}, {"downstream_provider": ["deepinfra", "groq"]},
    {"downstream_provider_name": "Groq"},
])
def test_host_pin_must_match_exact_route_and_boolean_authorization(monkeypatch, change):
    calls = transport_fixture(monkeypatch)
    key = free_key()
    key["game_free_pin"].update(change)
    with pytest.raises(providers.GameProviderError):
        providers.complete_free(key, "private fixture", 32)
    assert calls == []


@pytest.mark.parametrize("cost", [None, True, "0", -1, 0.01, math.nan, math.inf, {}, []])
def test_unknown_nonzero_and_malformed_response_costs_fail_closed(monkeypatch, cost):
    response = free_response()
    response["usage"]["cost"] = cost
    transport_fixture(monkeypatch, response=response)
    with pytest.raises(providers.GameProviderError):
        providers.complete_free(free_key(), "scene", 32)


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(provider="Groq"),
    lambda value: value.pop("provider"),
    lambda value: value.update(model="meta-llama/llama-3.2-3b-instruct"),
    lambda value: value.update(model="vendor/other:free"),
    lambda value: value.update(object="response"),
    lambda value: value.update(id=None),
    lambda value: value.update(endpoint="https://proxy.invalid"),
    lambda value: value.update(cost="unknown"),
    lambda value: value.update(route="fallback"),
    lambda value: value.update(fallback=True),
    lambda value: value.update(error={"message": "failed"}),
    lambda value: value["usage"].update(total_cost=0.1),
    lambda value: value["usage"].update(cost=10 ** 1000),
    lambda value: value["usage"].update(is_byok=True),
    lambda value: value["usage"].pop("is_byok"),
    lambda value: value["usage"].update(cost_details={"upstream_inference_cost": "0"}),
    lambda value: value["usage"].update(cost_details={"upstream_inference_cost": 0.1}),
    lambda value: value["usage"].update(completion_tokens=33),
    lambda value: value["usage"].update(completion_tokens=True),
    lambda value: value["choices"][0].update(finish_reason="tool_calls"),
    lambda value: value["choices"].append(copy.deepcopy(value["choices"][0])),
    lambda value: value["choices"][0]["message"].update(content=None),
    lambda value: value["choices"][0]["message"].update(content={"type": "text", "text": "bad"}),
    lambda value: value["choices"][0]["message"].update(content=" "),
    lambda value: value["choices"][0]["message"].update(content="x" * 1025),
    lambda value: value["choices"][0]["message"].update(tool_calls=[{"function": {"name": "shell"}}]),
    lambda value: value["choices"][0]["message"].update(function_call={"name": "shell"}),
    lambda value: value["usage"].update(server_tool_use_details={"tool_calls_executed": 1, "tool_calls_requested": 1}),
])
def test_free_text_usage_and_actual_destination_are_validated(monkeypatch, mutation):
    response = free_response()
    mutation(response)
    transport_fixture(monkeypatch, response=response)
    with pytest.raises(providers.GameProviderError):
        providers.complete_free(free_key(), "scene", 32)


def test_explicit_router_metadata_can_prove_single_provider_and_detect_fallback(monkeypatch):
    response = free_response()
    response.pop("provider")
    response["openrouter_metadata"] = {"attempt": 1, "is_byok": False, "requested": response["model"],
        "endpoints": {"total": 1, "available": [{"model": response["model"], "provider": "DeepInfra", "selected": True}]}}
    transport_fixture(monkeypatch, response=response)
    assert providers.complete_free(free_key(), "scene", 32)["provider"] == "DeepInfra"
    response["openrouter_metadata"]["attempt"] = 2
    transport_fixture(monkeypatch, response=response)
    with pytest.raises(providers.GameProviderError):
        providers.complete_free(free_key(), "scene", 32)


def test_local_verification_precedes_prompt_and_records_exact_actual_model(monkeypatch):
    calls = transport_fixture(monkeypatch, response=local_response())
    result = providers.complete_local(local_key(), "Authorized scene.", 48)
    assert result["provider"] == "ollama" and result["model"] == "campaign:fixture"
    assert result["destination"] == "local" and result["endpoint"] == providers.LOCAL_BASE + "/api/chat"
    assert len(calls) == 2
    assert calls[0][1] == {"model": "campaign:fixture", "verbose": False}
    assert "Authorized scene" not in json.dumps(calls[0])
    chat = calls[1][1]
    assert chat["options"] == {"num_ctx": 8192, "num_predict": 48, "temperature": 0.3}
    assert chat["stream"] is False and chat["think"] is False and "tools" not in chat
    assert calls[0][3] == calls[1][3]


@pytest.mark.parametrize("metadata", [
    {}, {**LOCAL_METADATA, "remote_host": "https://cloud.invalid"}, {**LOCAL_METADATA, "remote_model": "paid-model"},
    {**LOCAL_METADATA, "details": {"format": "gguf", "remote_host": "https://cloud.invalid"}},
    {**LOCAL_METADATA, "details": {"format": "cloud"}}, {**LOCAL_METADATA, "model_info": {}},
    {**LOCAL_METADATA, "capabilities": ["embedding"]},
])
def test_local_cloud_or_unverifiable_model_is_refused_before_chat(monkeypatch, metadata):
    calls = transport_fixture(monkeypatch, metadata=metadata)
    with pytest.raises(providers.GameProviderError):
        providers.complete_local(local_key(), "private scene", 32)
    assert len(calls) == 1 and calls[0][0].endswith("/api/show")
    assert "private scene" not in json.dumps(calls)


@pytest.mark.parametrize("change", [
    {"model": "campaign"}, {"model": "campaign:cloud"}, {"provider": "codex"},
    {"base_url": "http://localhost:11435"}, {"base_url": "http://127.0.0.1:11434/"},
    {"base_url": "https://api.ollama.com"}, {"base_url": "http://127.0.0.1.evil.invalid:11434"},
])
def test_local_proxy_and_model_aliases_never_dispatch(monkeypatch, change):
    calls = transport_fixture(monkeypatch)
    key = local_key()
    key.update(change)
    with pytest.raises(providers.GameProviderError):
        providers.complete_local(key, "scene", 32)
    assert calls == []


@pytest.mark.parametrize("change", [
    {"model": "another:fixture"}, {"done": False}, {"done_reason": "tool_calls"}, {"eval_count": None}, {"eval_count": 33},
    {"message": {"role": "assistant", "content": None}},
    {"message": {"role": "assistant", "content": "text", "tool_calls": [{"function": {"name": "shell"}}]}},
])
def test_local_response_model_tools_and_budget_are_checked(monkeypatch, change):
    response = local_response()
    response.update(change)
    transport_fixture(monkeypatch, response=response)
    with pytest.raises(providers.GameProviderError):
        providers.complete_local(local_key(), "scene", 32)


@pytest.mark.parametrize("maximum,prompt", [(True, "text"), (0, "text"), (6001, "text"), (32, ""), (32, "x" * 24001)])
def test_invalid_request_budget_never_dispatches(monkeypatch, maximum, prompt):
    calls = transport_fixture(monkeypatch)
    for operation, key in [(providers.complete_local, local_key()), (providers.complete_free, free_key())]:
        with pytest.raises(providers.GameProviderError):
            operation(key, prompt, maximum)
    assert calls == []


class FakeSocket:
    def __init__(self):
        self.aborted = threading.Event()
    def settimeout(self, timeout):
        assert timeout > 0
    def shutdown(self, how):
        self.aborted.set()


class FakeConnection:
    instances = []
    content = b'{"ok":true}'
    status = 200
    declared = None
    encoding = None
    def __init__(self, host, port, timeout):
        self.address = (host, port)
        self.sock = FakeSocket()
        self.original_socket = self.sock
        self.closed = False
        self.calls = []
        self.content_stream = io.BytesIO(self.content)
        self.__class__.instances.append(self)
    def connect(self):
        pass
    def request(self, method, path, body, headers):
        self.calls.append((method, path, body, headers))
    def getresponse(self):
        return self
    def getheader(self, name):
        return {"Content-Length": self.declared, "Content-Encoding": self.encoding}.get(name)
    def read1(self, count):
        return self.content_stream.read(count)
    def close(self):
        self.closed = True


def test_transport_uses_fixed_direct_tls_host_and_ignores_proxy_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setattr(providers.http.client, "HTTPSConnection", FakeConnection)
    assert providers._request_json(providers.FREE_ENDPOINT, {"model": "fixture"}, {}, time.monotonic() + 1) == {"ok": True}
    connection = FakeConnection.instances[-1]
    assert connection.address == ("openrouter.ai", 443)
    assert connection.calls[0][0:2] == ("POST", "/api/v1/chat/completions")
    assert connection.closed and len(connection.calls) == 1


@pytest.mark.parametrize("status,content,declared,encoding", [
    (302, b"", None, None), (307, b"", None, None), (429, b"private response", None, None),
    (200, b"x" * 262145, None, None), (200, b"{}", "262145", None),
    (200, b"{}", "-1", None), (200, b"{}", None, "gzip"),
    (200, b"[]", None, None), (200, b"not json", None, None),
    (200, b'{"cost":0,"cost":3}', None, None), (200, b'{"cost":NaN}', None, None),
], ids=["302", "307", "quota", "oversize-body", "oversize-header", "negative-length", "encoding", "array", "invalid-json", "duplicate-key", "nan"])
def test_transport_redirects_quotas_oversize_and_ambiguous_json_fail_closed(monkeypatch, status, content, declared, encoding):
    monkeypatch.setattr(FakeConnection, "status", status)
    monkeypatch.setattr(FakeConnection, "content", content)
    monkeypatch.setattr(FakeConnection, "declared", declared)
    monkeypatch.setattr(FakeConnection, "encoding", encoding)
    monkeypatch.setattr(providers.http.client, "HTTPSConnection", FakeConnection)
    with pytest.raises(providers.GameProviderError) as error:
        providers._request_json(providers.FREE_ENDPOINT, {"model": "fixture"}, {}, time.monotonic() + 1)
    assert "private response" not in str(error.value)
    assert FakeConnection.instances[-1].closed and len(FakeConnection.instances[-1].calls) == 1


def test_deadline_interrupts_detached_response_socket(monkeypatch):
    class SlowResponse(FakeConnection):
        def getresponse(self):
            self.sock = None
            return self
        def read1(self, count):
            assert self.original_socket.aborted.wait(1)
            raise OSError("interrupted")
    monkeypatch.setattr(providers.http.client, "HTTPSConnection", SlowResponse)
    started = time.monotonic()
    with pytest.raises(providers.GameProviderError):
        providers._request_json(providers.FREE_ENDPOINT, {"model": "fixture"}, {}, started + 0.04)
    assert time.monotonic() - started < 0.8
    assert SlowResponse.instances[-1].original_socket.aborted.wait(0.5)


def test_dns_finishing_after_deadline_cannot_send_prompt(monkeypatch):
    release, done = threading.Event(), threading.Event()
    class SlowConnect(FakeConnection):
        def connect(self):
            assert release.wait(1)
        def close(self):
            self.closed = True
            done.set()
    monkeypatch.setattr(providers.http.client, "HTTPSConnection", SlowConnect)
    try:
        with pytest.raises(providers.GameProviderError):
            providers._request_json(providers.FREE_ENDPOINT, {"prompt": "never sent"}, {}, time.monotonic() + 0.04)
    finally:
        release.set()
    assert done.wait(0.5)
    assert SlowConnect.instances[-1].calls == []
