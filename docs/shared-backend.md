# Shared Obus backend on this PC

All desktop and MCP clients use `http://127.0.0.1:38173`.
OpenAI-compatible clients use `http://127.0.0.1:38174/v1`, model `gpt-oss:20b`.
The bridge's `OBus` model alias remains supported.

The local installation enables `OBUS_ALLOW_LOCAL_CLIENTS=1` on the bridge.
Native loopback callers need no API key (use `local` if a client requires a nonempty field).
Requests from unrelated browser origins remain rejected, and the bridge binds to loopback.
Other installations retain key authentication unless local client access is explicitly enabled.

Windows runtime data lives in `%LOCALAPPDATA%\OBus`; `OCCULTBUS_HOME` can explicitly override it.
Both source and desktop launches use this folder. The bridge prefers the current source
launcher; setting `OBUS_EXE` explicitly selects a packaged runtime instead.

The desktop reuses the shared backend. It never selects a random private port and
closing its window leaves the backend available. A healthy incompatible backend
produces an update message instead of a second server.

Run `start_obus_hermes_bridge.ps1` to start the local bridge and backend.
The installed shared-backend sign-in task runs this service for the signed-in user.
It serves applications on this PC, including applications in other local sessions,
while that user session is active. The backend is not exposed to the LAN.
