"""Exercise the real Windows ConPTY terminal without starting the full UI."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import uuid

from backend.terminal_runtime import TerminalSession


MARKER = "OBUS_CONPTY_READY"


async def smoke(cwd: Path) -> None:
    session = TerminalSession(
        session_id=f"smoke-{uuid.uuid4().hex[:8]}",
        shell="pwsh",
        cwd=cwd.resolve(),
        rows=30,
        cols=100,
    )
    queue = session.subscribe()
    try:
        await session.start()
        await session.write(f"Write-Output '{MARKER}'\r")
        output = ""
        deadline = asyncio.get_running_loop().time() + 15
        while MARKER not in output:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"ConPTY did not emit {MARKER!r}; output={output!r}")
            chunk = await asyncio.wait_for(queue.get(), timeout=remaining)
            if chunk is None:
                pty = session._pty
                exitstatus = getattr(pty, "exitstatus", None) if pty is not None else None
                raise RuntimeError(
                    f"ConPTY exited before the marker; exitstatus={exitstatus!r}; output={output!r}"
                )
            output += chunk
        await session.resize(rows=35, cols=120)
        snapshot = session.snapshot()
        if not snapshot["alive"]:
            raise RuntimeError(f"ConPTY died during smoke test: {snapshot!r}")
        print(
            f"{MARKER} shell={snapshot['shell']} cwd={snapshot['cwd']} "
            f"size={snapshot['cols']}x{snapshot['rows']}"
        )
    finally:
        session.unsubscribe(queue)
        await session.close()


if __name__ == "__main__":
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    asyncio.run(smoke(root))
