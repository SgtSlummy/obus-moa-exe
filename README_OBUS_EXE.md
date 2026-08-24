# OBus EXecutable - Fully Contained MOA Runtime

A fully portable Windows EXE that bundles the complete OccultBus Mixture-of-Agents runtime with Tarot card routing, Solomon's Keys management, and RAG-based task matching.

## What This Provides

- **Single EXE launcher** - No Python/Node/venv required to run
- **Bundled FastAPI backend** with all provider integrations
- **Embedded static frontend SPA** - Modern React-based UI
- **Dynamic Tarot/Solomon's routing** - No static card→key pairings
- **Up to 20 concurrent specialist agents** with aggregators
- **Encrypted key storage** using Windows DPAPI
- **Local RAG** with bounded retrieval (five snippets, configurable 800–8000 character budget; 2,400 default) across durable OBus memory, Hermes memory, MemPalace, Mem0, and Tarot Router FTS5
- **Durable memory CRUD** in the Memory screen: add, tag, search, list, delete, and clear; atomic JSON persistence under `%LOCALAPPDATA%\OBus\memory.json`
- **Automatic route memory** (enabled by default): every completed prompt + final answer is redacted, bounded, deduplicated, persisted, and available to future RAG; disable it in Settings
- **Native MCP server**: run `OBus.exe --mcp` for eight stdio tools covering status, connection info, memory search/add, route plans/execution, and Tentacle Worm hardening status/runs
- **Tentacle Worm startup red team**: Scout, Red-Team, Hardener, and Verifier agents run in the background on first install and startup; the connected local LLM performs advisory analysis while deterministic allowlisted repairs handle setup, troubleshooting, hardening, and verification
- **Token and throughput controls**: adjustable 800–8000 character RAG budget, 1–20 parallel-agent ceiling, and a bounded 8-advisor Throughput profile
- **Animated kawaii agent state faces** in live MoA windows and Tarot agent cards
- **Zero external dependencies** at runtime

## Quick Start

1. **Download `OBus.exe`** from the dist folder
2. **Double-click to run** - Browser opens automatically to the UI
3. **Configure providers** in the Providers tab (add environment variable references only)
4. **Verify keys** using the verification wizard
5. **Submit tasks** in the Route Planner tab

## Default Verified Keys (Built-in)

| Key ID | Provider | Model | Role |
|--------|----------|-------|------|
| key-codex-oauth | OpenAI Codex | gpt-5.6-terra | Final aggregator |
| key-local-ollama | Local Ollama | gpt-oss:20b | Routing/scouting |
| key-nous-oauth | Nous | upstage/solar-pro4:free | Generalist |
| key-nvidia-nim | NVIDIA NIM | nvidia/nemotron-3-super-120b-a12b | Reasoning/research |

## Permanent Setup (Run Once)

Execute the setup script to configure permanent Occult Router permissions:

```powershell
# As Administrator (for system-wide setup)
powershell -ExecutionPolicy Bypass -File "install_obus_permanent.ps1"

# Or manually add to PATH via:
# System Properties > Environment Variables > Add OBus to PATH
```

## Standalone window, tray lifecycle, and usage

OBus opens in Microsoft Edge app mode: a standalone window with no tabs or
address bar. Closing that window leaves the warm backend running in the Windows
notification area. Use the **OBus** tray icon to **Open OBus** again or choose
**Exit OBus** to stop the runtime.

The dashboard reports the loaded model's runtime context window from Ollama's
`/api/ps`, last-route and cumulative local token usage, model-call count, and
route latency. Token values are provider-reported for local specialist,
synthesis, and verification calls. The external GPT 5.6 Luna CLI stage is
counted as a call and timed, but its token count is explicitly unavailable.
Usage history is retained in `%LOCALAPPDATA%\\OBus\\usage.json` (last 500 routes).

## Warm GPU and performance profiles

OBus now preloads the configured local Ollama model at startup and requests
`keep_alive: -1`, keeping it resident until Ollama or OBus is stopped. The
dashboard shows `GPU cold`, `GPU warming`, or `GPU warm` and provides a real
**Warm GPU** action backed by `POST /api/warmup`.

The Route panel exposes three bounded local-MoA profiles:

- **Fast** — 2 advisors / 2 workers / 384 output tokens
- **Balanced** (default) — 3 advisors / 3 workers / 512 output tokens
- **Deep** — 5 advisors / 5 workers / 768 output tokens

Set `OBUS_OLLAMA_KEEP_ALIVE` before launch to override the default indefinite
residency policy. Warmups accept installed Ollama model names only and run as a
single-flight operation: overlapping requests receive HTTP 202 with
`status: busy` and the in-flight model. No credential values are accepted or
returned by the warmup API.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (returns JSON) |
| `/api/provider/connection` | GET | Secret-safe OBus provider base URL, model, key reference, and live bridge state |
| `/api/route/plan` | POST | Get the dynamic Tarot/Key MOA routing plan |
| `/api/route/run` | POST | Execute the full local-first MOA and return the visible stage trace |
| `/api/rooms/{room_id}/run` | POST | Run a persisted council with incremental deliberation messages |
| `/` | GET | Frontend SPA entry point |

## Connect OBus to Hermes or another OpenAI-compatible client

OBus exposes a local OpenAI-compatible bridge. The dashboard shows these values live:

- Provider: `obus`
- Base URL / IP: `http://127.0.0.1:38174/v1`
- Model: `OBus`
- API-key reference: `OCCULTBUS_API_KEY` (the value is never displayed)
- Models endpoint: `http://127.0.0.1:38174/v1/models`
- Chat endpoint: `http://127.0.0.1:38174/v1/chat/completions`

For autonomous use, launch `OBus.exe --headless`. This starts the local API on
`127.0.0.1:38173` without opening Edge, a system-tray icon, or the desktop UI.
The `obus_hermes_bridge.py` supervisor always launches OBus with this flag and
uses the current `dist\OBus.exe` when available (falling back to the source
launcher for development). Set `OBUS_PORT` only when an isolated local runtime
is needed.

The default bridge is loopback-only. Set `OBUS_BRIDGE_HOST` explicitly only when
you intend to expose it on another interface and have configured
`OCCULTBUS_API_KEY`. In Hermes, the named provider entry belongs under
`providers.obus` with `api`, `default_model`, `key_env`, and
`transport: chat_completions`.

The Route panel opens one visual window per real MOA event. It first shows the
planned Tarot specialists as running, then replaces those placeholders with the
actual specialist outputs emitted by the local MoA router, followed by local
synthesis, verification, and the final external aggregate when available.

## Configuration

State is stored in `%LOCALAPPDATA%\OccultBus\` by default:

- `config/` - JSON configuration files
- `state.db` - Encrypted SQLite database
- `logs/` - Runtime logs
- `knowledge/` - RAG index files

To use a custom state directory:

```powershell
$env:OCCULTBUS_HOME="C:\MyStatePath"
.\OBus.exe
```

## Build From Source

```powershell
# Install Python 3.11+ and pip
pip install -r requirements.txt
pyinstaller OBus.spec
# Or: pyinstaller --onefile --name OBus obus_launcher.py
```

## Warp-inspired agent workspace

OBus now offers three configurable workspace surfaces in Setup:

- **Terminal** — route composer, live execution output, status, command palette, and portable settings.
- **Operator** — Terminal plus Cards & Keys, Tarot personas, persistent agents, rooms, receipts, routing, and Memory.
- **ADE** — the complete OBus surface, including Forums, Arcana Forge, Tentacle Worm safety, and integrations.

Press **Ctrl+K** (or **Cmd+K**) to open the searchable command palette. It can focus a route, switch pages, refresh live state, warm the local GPU, open Settings/Memory/Rooms, and export the latest receipt. **Ctrl+L** focuses the route composer, and **Escape** closes transient UI or returns focus to the composer.

The AUI is modeled after the useful WarpUI patterns rather than embedding Warp's implementation. `backend/aui.py` owns a versioned, secret-free action and accessibility manifest exposed at `/api/aui/manifest`. It describes surface-bounded actions, keyboard bindings, accessible view roles/value/help, and live-region principles. The SPA loads this contract into the command palette and the visible AUI action rail; action execution remains bound to OBus's existing route, room, receipt, runtime, and workspace functions. The Run workbench also supports compact/comfortable/spacious density, sidebar collapse, responsive viewport modes, route re-input/retry, and bounded workspace file filtering. See `docs/obus-aui.md` and `docs/obus-aui-research.md` for the full interaction model and provenance.

The local workspace context panel is explicitly **read-only local context**. Its status and bounded inspection APIs are exposed at `/api/workspace/status`, `/api/workspace/tree`, `/api/workspace/file`, and `/api/workspace/diff`. Configure a root manually; OBus bounds depth, file count, bytes, and text lines, rejects traversal/symlink escapes, omits secret-shaped files, and never runs a shell command. A selected bounded text file can be inserted into the next route.

## Portable settings

`GET /api/settings/export` returns a versioned `obus-settings.json` containing only non-secret UI, routing, model, deck, RAG, memory, workspace-surface, and workspace-root preferences. `POST /api/settings/import` validates and merges the same allowlist. It never imports provider credentials, OAuth tokens, machine access-gate state, machine role, private-key contents, or room/memory data.

## Routing policy and open models

Setup exposes **Local-first**, **Auto (open)**, and **Manual** routing policies. Auto (open) only considers Ready, connected Keys explicitly marked local/open-model, excludes the reserved GPT 5.6 Luna aggregate, honors cooldowns, and returns honest offline planning when no eligible open model is available. Tarot card-to-Key choices remain temporary and are never persisted by automatic planning.

## Run receipts

Every offline, partial, and complete `/api/route/run` response includes a redacted receipt summary. Receipts are available through `/api/runs`, `/api/runs/{receipt_id}`, and `/api/runs/{receipt_id}/export`. They contain a prompt hash, route plan, temporary assignment metadata, trace, usage, status, and bounded final output. Raw prompt text, credentials, private room transcripts, and private-key material are excluded. Receipt exports may still contain task output; the UI labels them as task-content handoffs.

## Troubleshooting

**OBus port 38173 in use** - Stop the other local OBus runtime or launch an isolated instance with `OBUS_PORT`.

**Provider bridge port 38174 in use** - Stop the conflicting local bridge or set an intentional bridge configuration.

**Browser doesn't open** - Navigate to `http://127.0.0.1:38173/` manually after confirming `/health` responds.

**Provider shows unverified** - Set the environment variable referenced in the provider record and re-verify.

**Logs** - Check `%LOCALAPPDATA%\OccultBus\logs\`

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OBus.exe (Single File)                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐               │
│  │  PyInstaller    │───▶│  FastAPI Server │               │
│  │  Bootloader     │    │   (uvicorn)     │               │
│  └─────────────────┘    └─────────────────┘               │
│                             │                               │
│  ┌──────────────────────────┼──────────────────────────┐   │
│  │        Static Assets     │    Backend Modules       │   │
│  │  ┌────────────────────┐  │  ┌────────────────────┐  │   │
│  │  │  Frontend SPA      │  │  │  tarot_router.py   │  │   │
│  │  │  (React/HTML/CSS)  │  │  │  tarot_moa.py     │  │   │
│  │  │                  │  │  │  tarot_agents.py  │  │   │
│  │  │                  │  │  │  tarot_rag.py     │  │   │
│  │  │                  │  │  │  solomons_keys   │  │   │
│  │  └────────────────────┘  │  └────────────────────┘  │   │
│  └──────────────────────────┴──────────────────────────┘   │
│                             │                               │
│  ┌──────────────────────────▼──────────────────────────┐   │
│  │                  Encrypted SQLite State              │   │
│  │  - Provider keys (DPAPI encrypted)                  │   │
│  │  - Card states and cooldowns                        │   │
│  │  - Verification records                               │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Identity Rule (Preserved from Tarot Router)

> Tarot cards are agent personas; Solomon's Keys are LLM/provider handles; RAG dynamically matches them per task; no static card/key pairing exists.

This means:
- Each session gets fresh card↔key assignments
- Task capabilities drive matching, not preferences
- Unverified keys are automatically excluded
- Cooldown state persists between runs

## Security Notes

- **Never** embeds API keys or OAuth tokens
- **Windows DPAPI** encrypts all stored credentials
- **Local-only** by default (binds to 127.0.0.1)
- **Environment references only** in UI (no secret input fields)
- **Offline planning mode** keeps rooms, forums, and route planning usable before any provider is configured

## Isolated Rooms and Chymeria Forum

OBus now supports AgentCouncil-style isolated rooms. Each room owns a Tarot hand/spread, a private council transcript, a collaborative or adversarial mode, and one Chymeria representative. Chymeria publishes one versioned decision packet for the room; other rooms receive packets through a Forum thread, never raw private card deliberation.

The implementation is documented in `docs/agentcouncil-rooms.md`. The primary endpoints are:

- `POST /api/rooms` and `POST /api/rooms/{room_id}/run`
- `POST /api/forum/threads`
- `POST /api/forum/threads/{thread_id}/round`

AgentCouncil is used as a protocol reference. OBus does not require Copilot CLI, does not vendor upstream files, and continues to enforce ready Solomon's Keys, provider cooldowns, and secret-safe authorization references.