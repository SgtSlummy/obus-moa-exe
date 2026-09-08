"""Restricted text-only provider transports for the private Obus game service.

No general Obus provider adapter, tool engine, proxy, model router, or fallback
is invoked here. Local inference requires a concrete local GGUF model before
any prompt is sent. Free inference requires an exact OpenRouter :free model,
one allowed downstream provider, hard zero-price ceilings and response cost /
provider evidence. A host pin is authorization, not independent billing proof.

Contracts checked 2026-09-08 against official API documentation:
https://openrouter.ai/docs/guides/routing/provider-selection
https://openrouter.ai/docs/guides/routing/model-variants/free
https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion

A supported contract does not establish model availability or account readiness.
Credentials are resolved only at dispatch from the selected Obus env reference.
No credentials, prompt text or provider response bodies are logged or persisted.
"""
from __future__ import annotations

import http.client
import json
import math
import os
import re
import socket
import threading
import time

LOCAL_BASE = "http://127.0.0.1:11434"
FREE_BASE = "https://openrouter.ai/api/v1"
FREE_ENDPOINT = FREE_BASE + "/chat/completions"
MAX_PROMPT_CHARS = 24000
MAX_REQUEST_BYTES = 160000
MAX_RESPONSE_BYTES = 262144
GENERATION_SECONDS = 90.0
_DOWNSTREAMS = {"chutes": "Chutes", "deepinfra": "DeepInfra", "novita": "NovitaAI", "groq": "Groq", "cerebras": "Cerebras"}
_HTTP_SLOTS = threading.BoundedSemaphore(2)
_TOOL_FIELDS = {"tool_calls", "function_call", "functions", "tools", "mcp_list_tools", "executed_tools", "tool_results"}


class GameProviderError(RuntimeError):
    """A route cannot satisfy the game's provider contract."""


def _remaining(deadline: float) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise GameProviderError("Game provider deadline elapsed")
    return value


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GameProviderError("Duplicate provider response fields")
        result[key] = value
    return result


def _json_constant(_value):
    raise GameProviderError("Non-finite provider response number")


def _request_json(endpoint: str, payload: dict, headers: dict, deadline: float) -> dict:
    """Fixed transports, no proxy/redirect/retry; deadline also bounds DNS waits.

    A timed-out DNS/TLS operation may finish later in its daemon worker. It
    retains a bounded slot, then checks cancellation before sending the prompt.
    At most two workers exist; expired requests cannot create an unbounded queue.
    """
    endpoints = {LOCAL_BASE + "/api/show": ("127.0.0.1", 11434, "/api/show", False),
                 LOCAL_BASE + "/api/chat": ("127.0.0.1", 11434, "/api/chat", False),
                 FREE_ENDPOINT: ("openrouter.ai", 443, "/api/v1/chat/completions", True)}
    if endpoint not in endpoints:
        raise GameProviderError("Unapproved game provider endpoint")
    try:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise GameProviderError("Invalid game provider request") from None
    if len(body) > MAX_REQUEST_BYTES:
        raise GameProviderError("Game provider request exceeds byte budget")
    _remaining(deadline)
    if not _HTTP_SLOTS.acquire(blocking=False):
        raise GameProviderError("Game provider transport is busy")
    cancelled, finished = threading.Event(), threading.Event()
    state, state_lock = {}, threading.Lock()

    def abort():
        cancelled.set()
        with state_lock:
            active_socket = state.get("socket")
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def work():
        connection = None
        try:
            host, port, path, secure = endpoints[endpoint]
            connection_type = http.client.HTTPSConnection if secure else http.client.HTTPConnection
            connection = connection_type(host, port, timeout=_remaining(deadline))
            connection.connect()
            with state_lock:
                state["socket"] = connection.sock
            if cancelled.is_set():
                raise GameProviderError("Game provider deadline elapsed")
            connection.sock.settimeout(_remaining(deadline))
            connection.request("POST", path, body=body, headers={"Content-Type": "application/json", **headers})
            response = connection.getresponse()
            if response.status != 200:
                raise GameProviderError("Game provider rejected the request")
            declared = response.getheader("Content-Length")
            if declared is not None and (not declared.isdigit() or int(declared) > MAX_RESPONSE_BYTES):
                raise GameProviderError("Invalid provider response length")
            encoding = response.getheader("Content-Encoding")
            if encoding not in (None, "identity"):
                raise GameProviderError("Unsupported provider response encoding")
            data = bytearray()
            while True:
                _remaining(deadline)
                chunk = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise GameProviderError("Game provider response exceeds byte budget")
            _remaining(deadline)
            result = json.loads(data, object_pairs_hook=_json_pairs, parse_constant=_json_constant)
            if not isinstance(result, dict):
                raise GameProviderError("Game provider response must be an object")
            state["result"] = result
        except (OSError, ValueError, TypeError, RecursionError, http.client.HTTPException, GameProviderError):
            # Never relay a remote response or authorization header in errors.
            state["error"] = GameProviderError("Game provider transport or response failed validation")
        finally:
            if connection is not None:
                connection.close()
            _HTTP_SLOTS.release()
            finished.set()

    worker = threading.Thread(target=work, name="obus-game-provider", daemon=True)
    try:
        worker.start()
    except RuntimeError:
        _HTTP_SLOTS.release()
        raise GameProviderError("Game provider transport could not start") from None
    if not finished.wait(max(0.0, deadline - time.monotonic())):
        abort()
        raise GameProviderError("Game provider deadline elapsed")
    _remaining(deadline)
    if "error" in state:
        raise state["error"]
    return state["result"]


def _request_parameters(key: dict, prompt: str, maximum: int) -> None:
    if not isinstance(key, dict) or key.get("connected") is not True or key.get("verified") is not True:
        raise GameProviderError("A verified connected game provider is required")
    if not isinstance(key.get("id"), str) or not 1 <= len(key["id"]) <= 160:
        raise GameProviderError("Game provider route identity is missing")
    if type(maximum) is not int or not 16 <= maximum <= 6000:
        raise GameProviderError("Game provider token budget must be 16 to 6000")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > MAX_PROMPT_CHARS:
        raise GameProviderError("Game provider prompt exceeds its text contract")


def _no_tools(value, depth=0) -> None:
    if depth > 16:
        raise GameProviderError("Provider metadata is too deeply nested")
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "error" and item is not None:
                raise GameProviderError("Provider returned an error response")
            if key in _TOOL_FIELDS and item not in (None, []):
                raise GameProviderError("Tool or function output is forbidden in game inference")
            if key in {"tool_calls_executed", "tool_calls_requested"} and (type(item) is not int or item != 0):
                raise GameProviderError("Provider executed or requested a tool")
            _no_tools(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _no_tools(item, depth + 1)


def _text(message: object, count: object, maximum: int) -> str:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise GameProviderError("Provider did not return an assistant text message")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip() or len(content) > 16000 or len(content.encode("utf-8")) > min(64000, maximum * 32):
        raise GameProviderError("Provider text is empty, malformed or outside its budget")
    if type(count) is not int or not 1 <= count <= maximum:
        raise GameProviderError("Provider completion token usage is missing or outside its budget")
    if re.search(r"<\s*/?\s*(?:tool_call|function_call)\b", content, re.IGNORECASE):
        raise GameProviderError("Serialized tool requests are forbidden")
    return content.strip()


def _local_model(key: dict) -> str:
    model = key.get("model")
    if key.get("provider") != "ollama" or key.get("base_url") not in (LOCAL_BASE, "http://localhost:11434"):
        raise GameProviderError("Local game inference requires the fixed loopback Ollama service")
    # Require an explicit tag. No bare-name/latest or proxy aliases are inferred.
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,140}:[A-Za-z0-9._-]{1,40}", model) or "cloud" in model.lower():
        raise GameProviderError("Local game inference requires an explicit local model tag")
    return model


def _require_local_completion(metadata: dict) -> None:
    details, info = metadata.get("details"), metadata.get("model_info")
    if not isinstance(details, dict) or details.get("format") != "gguf" or not isinstance(info, dict) or not isinstance(info.get("general.architecture"), str) or not info["general.architecture"]:
        raise GameProviderError("Selected game model is not a concrete local GGUF model")
    capabilities = metadata.get("capabilities")
    if not isinstance(capabilities, list) or "completion" not in capabilities:
        raise GameProviderError("Selected local model does not support completion")
    if any(value for key, value in metadata.items() if key.startswith("remote_")) or any(value for key, value in details.items() if key.startswith("remote_")):
        raise GameProviderError("Cloud-backed local model routes are forbidden")


def complete_local(key: dict, prompt: str, maximum: int) -> dict:
    """Complete through verified local Ollama; return actual model provenance."""
    deadline = time.monotonic() + GENERATION_SECONDS
    _request_parameters(key, prompt, maximum)
    model = _local_model(key)
    metadata = _request_json(LOCAL_BASE + "/api/show", {"model": model, "verbose": False}, {}, deadline)
    _require_local_completion(metadata)
    response = _request_json(LOCAL_BASE + "/api/chat", {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False,
        "options": {"num_ctx": 8192, "num_predict": maximum, "temperature": 0.3}}, {}, deadline)
    _no_tools(response)
    if response.get("model") != model or response.get("done") is not True or response.get("done_reason") not in ("stop", "length"):
        raise GameProviderError("Local provider model or completion provenance is invalid")
    text = _text(response.get("message"), response.get("eval_count"), maximum)
    return {"text": text, "provider": "ollama", "model": response["model"], "endpoint": LOCAL_BASE + "/api/chat", "route_id": key["id"],
            "destination": "local", "cost": "zero", "cost_basis": "local-inference", "completion_tokens": response["eval_count"], "finish_reason": response["done_reason"]}


def _free_pin(key: dict) -> dict:
    pin, model = key.get("game_free_pin"), key.get("model")
    if key.get("provider") != "openrouter" or key.get("base_url") != FREE_BASE:
        raise GameProviderError("No cost-enforcing free transport is available for this provider")
    if not isinstance(pin, dict) or any(pin.get(name) is not True for name in ("zero_charge", "no_fallback", "no_tools")):
        raise GameProviderError("Explicit free game route authorization is missing")
    if any(pin.get(name) != key.get(name) for name in ("id", "provider", "model", "base_url")):
        raise GameProviderError("Game free route does not match its host pin")
    if not isinstance(model, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,70}/[a-z0-9][a-z0-9._-]{0,100}:free", model) or model.startswith("openrouter/") or any(word in model for word in ("auto", "router", "compound", "codex", "random")):
        raise GameProviderError("A concrete free model is required; model routers and paid variants are forbidden")
    downstream = pin.get("downstream_provider")
    if not isinstance(downstream, str) or downstream not in _DOWNSTREAMS or pin.get("downstream_provider_name") != _DOWNSTREAMS[downstream]:
        raise GameProviderError("A supported exact downstream provider pin is required")
    return pin


def _zero(value: object) -> bool:
    return type(value) in (int, float) and value == 0 and math.isfinite(value)


def _free_usage(response: dict, maximum: int) -> tuple[dict, dict, str]:
    usage = response.get("usage")
    if not isinstance(usage, dict) or not _zero(usage.get("cost")) or usage.get("is_byok") is not False:
        raise GameProviderError("Free response lacks verified zero-cost non-BYOK usage")
    if any(name in usage for name in ("total_cost", "price", "billing", "charged", "provider", "model")):
        raise GameProviderError("Provider usage contains unsupported cost or routing fields")
    costs = usage.get("cost_details")
    if costs is not None and (not isinstance(costs, dict) or any(not _zero(value) for value in costs.values() if value is not None)):
        raise GameProviderError("Provider response contains nonzero or malformed costs")
    if any(name in response for name in ("cost", "billing", "route", "models", "usage_breakdown")):
        raise GameProviderError("Provider response contains unsupported routing or billing metadata")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise GameProviderError("Exactly one provider completion is required")
    choice = choices[0]
    if choice.get("index") != 0 or type(choice.get("index")) is not int or choice.get("finish_reason") not in ("stop", "length"):
        raise GameProviderError("Provider completion did not finish as text")
    text = _text(choice.get("message"), usage.get("completion_tokens"), maximum)
    return usage, choice, text


def _free_provenance(response: dict, key: dict, pin: dict) -> str:
    if response.get("model") != key["model"] or response.get("object") != "chat.completion":
        raise GameProviderError("Free provider changed the pinned model")
    if "fallback" in response and response["fallback"] is not False:
        raise GameProviderError("Free provider reported a fallback")
    provider = response.get("provider")
    metadata = response.get("openrouter_metadata")
    if metadata is not None:
        if not isinstance(metadata, dict) or metadata.get("is_byok") is not False or metadata.get("requested") != key["model"] or type(metadata.get("attempt")) is not int or metadata["attempt"] != 1:
            raise GameProviderError("Free provider routing provenance is invalid")
        endpoints = metadata.get("endpoints")
        available = endpoints.get("available") if isinstance(endpoints, dict) else None
        if not isinstance(available, list) or len(available) != 1 or type(endpoints.get("total")) is not int or endpoints["total"] != 1 or not isinstance(available[0], dict) or available[0].get("selected") is not True:
            raise GameProviderError("Free provider used an unapproved endpoint set")
        selected = available[0]
        if selected.get("model") != key["model"] or selected.get("provider") != pin["downstream_provider_name"]:
            raise GameProviderError("Free provider selected a different model or destination")
        if provider is not None and provider != selected["provider"]:
            raise GameProviderError("Free provider provenance is contradictory")
        provider = selected["provider"]
    if provider != pin["downstream_provider_name"]:
        raise GameProviderError("Free provider did not prove its pinned downstream destination")
    if "endpoint" in response and response["endpoint"] != FREE_ENDPOINT:
        raise GameProviderError("Free provider endpoint provenance is invalid")
    return provider


def complete_free(key: dict, prompt: str, maximum: int) -> dict:
    """Single pinned :free model/provider, zero-price request, checked actual cost."""
    deadline = time.monotonic() + GENERATION_SECONDS
    _request_parameters(key, prompt, maximum)
    pin = _free_pin(key)
    env_var = key.get("env_var")
    if not isinstance(env_var, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,99}", env_var):
        raise GameProviderError("Game provider credential reference is invalid")
    secret = os.environ.get(env_var)
    if not isinstance(secret, str) or not 1 <= len(secret) <= 4096 or any(ord(char) < 33 or ord(char) > 126 for char in secret):
        raise GameProviderError("Game provider credential is unavailable")
    response = _request_json(FREE_ENDPOINT, {"model": key["model"], "messages": [{"role": "user", "content": prompt}], "max_tokens": maximum,
        "stream": False, "tool_choice": "none", "parallel_tool_calls": False, "usage": {"include": True},
        "provider": {"order": [pin["downstream_provider"]], "only": [pin["downstream_provider"]], "allow_fallbacks": False,
                     "require_parameters": True, "max_price": {"prompt": 0, "completion": 0, "request": 0, "image": 0}}},
        {"Authorization": "Bearer " + secret}, deadline)
    _no_tools(response)
    usage, choice, text = _free_usage(response, maximum)
    provider = _free_provenance(response, key, pin)
    response_id = response.get("id")
    if not isinstance(response_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", response_id):
        raise GameProviderError("Provider response identity is invalid")
    return {"text": text, "provider": provider, "model": response["model"], "endpoint": FREE_ENDPOINT, "route_id": key["id"], "gateway": "openrouter",
            "destination": "external", "cost": "zero", "cost_basis": "free-variant+zero-price-ceiling+response-usage", "completion_tokens": usage["completion_tokens"],
            "finish_reason": choice["finish_reason"], "response_id": response_id}
