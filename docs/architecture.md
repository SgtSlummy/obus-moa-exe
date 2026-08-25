# Obus architecture

## System boundary

Obus is a local application composed of one FastAPI process, a static browser UI served by that process, persistent state under `OCCULTBUS_HOME`, provider/agent subprocesses, and an optional Windows launcher. The backend is the authority for state, security checks, provider lifecycle, routing, cancellation, health and integrations. The UI communicates only through same-origin HTTP APIs.

## Components

- `backend/main.py`: application composition, HTTP routes, access middleware, state migration and runtime orchestration.
- `backend/persistent_agents.py`: Codex and remote-provider execution, validation and agent lifecycle.
- `backend/static/`: operator UI and modular AUI assets.
- `backend/memory_store.py` and state helpers: local persistence with bounded, atomic writes.
- `tools/obus_launcher/`: single-instance health-aware desktop startup and Windows packaging.
- `tests/`: application, integration, UI-contract, security-boundary and persistence coverage.
- `.github/workflows/ci.yml`: clean cross-platform verification and Windows artifact production.

## Request and agent flow

1. The launcher starts the backend only when `/health` is unavailable.
2. The browser opens immediately after health succeeds; noncritical warmup follows.
3. The UI loads state and provider availability through same-origin APIs.
4. New state selects `key-codex-oauth` as aggregator and primary runtime key. Explicit persisted selections win.
5. Codex authentication and execution remain owned by the Codex CLI. Other providers use validated endpoints and environment-variable references.
6. Runtime events, cancellation signals and receipts flow back through backend-owned state; secrets are redacted before persistence or display.

## Persistence and security

Runtime data lives outside the checkout. JSON state writes use locks, temporary files, `fsync`, and atomic replacement. Access middleware supports a machine-bound local password session. Provider URLs are validated, workspace reads are bounded, known credential paths and secret-shaped content are rejected or redacted, and CI uses read-only repository permissions.

## Startup and shutdown

Health is the only launch gate. Optional providers, GPU/model warming, GitHub synchronization and local studios must not prevent the UI becoming available. Uvicorn owns server signal handling and graceful connection shutdown. Agent and route cancellation use bounded events; production operators should stop the foreground process with Ctrl+C or send the service manager's normal termination signal before forcing termination.

## Production modes

- Development: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 38173 --reload`
- Source production: omit `--reload`, keep loopback binding unless a trusted reverse proxy and access policy are configured.
- Windows desktop: build `Obus.exe`; the launcher manages backend readiness and opens the local UI.

External integrations are optional capabilities, not startup dependencies. Failures must be surfaced as provider/integration status without taking down the core application.
