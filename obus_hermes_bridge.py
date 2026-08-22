"""OpenAI-compatible local bridge for the OBus MOA desktop runtime."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

OBUS_EXE = Path(os.getenv("OBUS_EXE", r"C:\Users\Hermes\OneDrive\OBus-MOA-Digital\OBus.exe"))
OBUS_URL = os.getenv("OBUS_URL", "http://127.0.0.1:38173").rstrip("/")
BRIDGE_HOST = os.getenv("OBUS_BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.getenv("OBUS_BRIDGE_PORT", "38174"))
LOG_PATH = Path(os.getenv("LOCALAPPDATA", Path.home())) / "OBus" / "logs" / "hermes-bridge.log"


class ObusRuntime:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def health(self) -> dict[str, Any]:
        try:
            request = Request(f"{OBUS_URL}/health", headers={"User-Agent": "OBus-Hermes-Bridge/1.0"})
            with urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return {"reachable": True, **payload}
        except (OSError, URLError, json.JSONDecodeError) as exc:
            return {"reachable": False, "error": type(exc).__name__}

    def ensure_running(self) -> dict[str, Any]:
        with self._lock:
            state = self.health()
            if state.get("reachable"):
                return state
            if not OBUS_EXE.is_file():
                raise RuntimeError(f"OBus executable not found: {OBUS_EXE}")
            if self._process is None or self._process.poll() is not None:
                log = LOG_PATH.open("a", encoding="utf-8", buffering=1)
                flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                self._process = subprocess.Popen(
                    [str(OBUS_EXE)],
                    cwd=OBUS_EXE.parent,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=flags,
                )
            for _ in range(60):
                state = self.health()
                if state.get("reachable"):
                    return state
                time.sleep(0.25)
            raise RuntimeError("OBus did not become healthy within 15 seconds")

    def stop(self) -> None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None


runtime = ObusRuntime()


def extract_prompt(messages: Any) -> str:
    if not isinstance(messages, list):
        return str(messages or "")[:32_000]
    lines: list[str] = []
    system_messages = [message for message in messages if isinstance(message, dict) and message.get("role") == "system"]
    conversation = [message for message in messages if isinstance(message, dict) and message.get("role") != "system"][-8:]
    for message in system_messages[:2] + conversation:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
        lines.append(f"{role}: {str(content)}")
    return "\n\n".join(lines)[-16_000:]


def run_obus(prompt: str, model: str) -> str:
    runtime.ensure_running()
    body = json.dumps({"prompt": prompt, "model": None, "deck_mode": "auto", "rag_enabled": True}).encode("utf-8")
    request = Request(
        f"{OBUS_URL}/api/route/run",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "OBus-Hermes-Bridge/1.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=360) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"OBus route failed: {type(exc).__name__}") from exc
    answer = str(payload.get("final", "")).strip()
    if not answer:
        raise RuntimeError("OBus returned an empty final answer")
    return answer


def completion_payload(model: str, answer: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-obus-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "OBus",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class BridgeHandler(BaseHTTPRequestHandler):
    def _json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            state = runtime.health()
            self._json({"status": "ok" if state.get("reachable") else "degraded", "service": "obus-hermes-bridge", "obus": state})
            return
        if self.path == "/v1/models":
            self._json({"object": "list", "data": [{"id": "OBus", "object": "model", "owned_by": "OBus"}]})
            return
        self._json({"error": {"message": "not found", "type": "invalid_request_error"}}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/v1/chat/completions":
            self._json({"error": {"message": "not found", "type": "invalid_request_error"}}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 256_000:
                raise ValueError("request body must be 1-256000 bytes")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            answer = run_obus(extract_prompt(payload.get("messages")), str(payload.get("model", "OBus")))
            self._json(completion_payload(str(payload.get("model", "OBus")), answer))
        except ValueError as exc:
            self._json({"error": {"message": str(exc), "type": "invalid_request_error"}}, HTTPStatus.BAD_REQUEST)
        except RuntimeError as exc:
            self._json({"error": {"message": str(exc), "type": "server_error"}}, HTTPStatus.BAD_GATEWAY)

    def log_message(self, format: str, *args) -> None:
        return


def serve(stop_event: threading.Event | None = None) -> None:
    server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), BridgeHandler)
    print(f"OBus Hermes bridge listening at http://{BRIDGE_HOST}:{BRIDGE_PORT}")
    try:
        if stop_event is None:
            server.serve_forever()
        else:
            server.timeout = 0.5
            while not stop_event.is_set():
                server.handle_request()
    finally:
        runtime.stop()
        server.server_close()


if __name__ == "__main__":
    serve()
