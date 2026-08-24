"""Secret-safe stdio MCP facade for the local OBus runtime."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

OBUS_API_URL = os.getenv("OBUS_URL", "http://127.0.0.1:38173").rstrip("/")
PROTOCOL_VERSION = "2025-06-18"


def serialize_message(message: dict[str, Any]) -> str:
    """Emit ASCII-safe JSON for Windows stdio code pages."""
    return json.dumps(message, ensure_ascii=True)


def request_json(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{OBUS_API_URL}{path}", data=data,
        headers={"Content-Type": "application/json", "User-Agent": "OBus-MCP/1.0"}, method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=480) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"OBus HTTP {exc.code}: {detail}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OBus is unavailable: {type(exc).__name__}") from exc


def tool_catalog() -> list[dict[str, Any]]:
    return [
        {"name": "obus_status", "description": "Read OBus runtime, provider, memory, GPU and routing status.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "obus_connection", "description": "Read secret-safe OpenAI-compatible OBus connection information.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "obus_memory_search", "description": "Search bounded local OBus, Hermes, MemPalace, Mem0 and Tarot RAG memory.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["query"]}},
        {"name": "obus_memory_add", "description": "Add a redacted, deduplicated durable OBus memory.", "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "maxLength": 8000}, "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 12}}, "required": ["text"]}},
        {"name": "obus_route_plan", "description": "Dry-run dynamic Tarot/Key routing with bounded RAG and no model execution.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "rag_enabled": {"type": "boolean"}, "performance_profile": {"type": "string", "enum": ["fast", "balanced", "deep", "throughput"]}}, "required": ["prompt"]}},
        {"name": "obus_deliberate_plan", "description": "Create a review-only plan from bounded parallel Tarot proposals and sanitized Chymeria decisions. It never executes tools or system actions.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "mode": {"type": "string", "enum": ["collaborative", "adversarial"]}}, "required": ["prompt"]}},
        {"name": "obus_route_run", "description": "Execute a full OBus route and return visible specialist trace plus final answer.", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}, "rag_enabled": {"type": "boolean"}, "performance_profile": {"type": "string", "enum": ["fast", "balanced", "deep", "throughput"]}, "model": {"type": "string"}}, "required": ["prompt"]}},
        {"name": "obus_tentacle_status", "description": "Read the latest first-install/startup Tentacle Worm hardening and verification report.", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "obus_tentacle_run", "description": "Run the bounded local-LLM Tentacle Worm red team with allowlisted safe repairs.", "inputSchema": {"type": "object", "properties": {"full": {"type": "boolean"}, "apply_safe_fixes": {"type": "boolean"}}}},
    ]


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    arguments = arguments or {}
    if name == "obus_status":
        return request_json("/api/dashboard")
    if name == "obus_connection":
        return request_json("/api/provider/connection")
    if name == "obus_memory_search":
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")
        limit = min(max(int(arguments.get("limit", 20)), 1), 50)
        return request_json(f"/api/memory/search?query={urllib.parse.quote(query)}&limit={limit}")
    if name == "obus_memory_add":
        return request_json("/api/memory", "POST", {"text": str(arguments.get("text", "")), "tags": arguments.get("tags", [])})
    if name == "obus_tentacle_status":
        return request_json("/api/tentacle-worms/status")
    if name == "obus_tentacle_run":
        return request_json("/api/tentacle-worms/run", "POST", {"full": bool(arguments.get("full", True)), "apply_safe_fixes": bool(arguments.get("apply_safe_fixes", True))})
    if name == "obus_deliberate_plan":
        prompt = str(arguments.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")
        mode = str(arguments.get("mode", "collaborative"))
        if mode not in {"collaborative", "adversarial"}:
            raise ValueError("mode must be collaborative or adversarial")
        return request_json("/api/plan/deliberate", "POST", {"prompt": prompt, "mode": mode})
    if name in {"obus_route_plan", "obus_route_run"}:
        prompt = str(arguments.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt is required")
        body = {
            "prompt": prompt,
            "rag_enabled": bool(arguments.get("rag_enabled", True)),
            "performance_profile": str(arguments.get("performance_profile", "balanced")),
        }
        if arguments.get("model"):
            body["model"] = str(arguments["model"])
        return request_json("/api/route/plan" if name == "obus_route_plan" else "/api/route/run", "POST", body)
    raise ValueError(f"unknown OBus tool: {name}")


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": {"name": "obus", "version": "1.0.0"}}}
    if method in {"notifications/initialized", "ping"} and request_id is None:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_catalog()}}
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            result = call_tool(str(params.get("name", "")), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}], "isError": False}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": request_id, "result": {"content": [{"type": "text", "text": str(exc)}], "isError": True}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve() -> None:
    for raw in sys.stdin:
        try:
            message = json.loads(raw)
            response = handle_request(message)
            if response is not None:
                sys.stdout.write(serialize_message(response) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(serialize_message({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve()
