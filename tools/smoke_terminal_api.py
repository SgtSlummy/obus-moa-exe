"""Smoke-test an OBus terminal API, including its WebSocket output stream."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from websockets.asyncio.client import connect


MARKER = "OBUS_PACKAGED_CONPTY_READY"


def request_json(url: str, method: str = "GET", payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urlopen(request, timeout=15) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


async def smoke(base_url: str, cwd: Path) -> None:
    session = request_json(
        f"{base_url}/api/terminal/sessions",
        "POST",
        {"shell": "pwsh", "cwd": str(cwd.resolve()), "rows": 30, "cols": 100},
    )
    session_id = session["id"]
    ws_url = base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    output = ""
    try:
        async with connect(f"{ws_url}/api/terminal/sessions/{session_id}/stream") as socket:
            await socket.send(json.dumps({"type": "input", "data": f"Write-Output '{MARKER}'\r"}))
            deadline = asyncio.get_running_loop().time() + 15
            while MARKER not in output:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"terminal WebSocket did not emit {MARKER!r}; output={output!r}")
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=remaining))
                if message.get("type") == "output":
                    output += str(message.get("data") or "")
                elif message.get("type") == "status" and not message.get("alive", True):
                    raise RuntimeError(f"terminal exited before marker; output={output!r}")
            await socket.send(json.dumps({"type": "resize", "rows": 35, "cols": 120}))
        resized = request_json(
            f"{base_url}/api/terminal/sessions/{session_id}/size",
            "PATCH",
            {"rows": 35, "cols": 120},
        )
        if not resized["alive"]:
            raise RuntimeError(f"terminal died after output: {resized!r}")
        print(
            f"{MARKER} shell={resized['shell']} cwd={resized['cwd']} "
            f"size={resized['cols']}x{resized['rows']}"
        )
    finally:
        request_json(f"{base_url}/api/terminal/sessions/{session_id}", "DELETE")


if __name__ == "__main__":
    url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8010"
    root = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path.cwd()
    asyncio.run(smoke(url, root))
