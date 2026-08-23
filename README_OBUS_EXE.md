# OBus EXecutable - Fully Contained MOA Runtime

A fully portable Windows EXE that bundles the complete OccultBus Mixture-of-Agents runtime with Tarot card routing, Solomon's Keys management, and RAG-based task matching.

## What This Provides

- **Single EXE launcher** - No Python/Node/venv required to run
- **Bundled FastAPI backend** with all provider integrations
- **Embedded static frontend SPA** - Modern React-based UI
- **Dynamic Tarot/Solomon's routing** - No static card→key pairings
- **Up to 20 concurrent specialist agents** with aggregators
- **Encrypted key storage** using Windows DPAPI
- **Local RAG** with bounded retrieval (five snippets / 3,200 characters) across durable OBus memory, Hermes memory, MemPalace, Mem0, and Tarot Router FTS5
- **Durable memory CRUD** in the Memory screen: add, tag, search, list, delete, and clear; atomic JSON persistence under `%LOCALAPPDATA%\OBus\memory.json`
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

## Troubleshooting

**Port 8080 in use** - Edit `config/default.json` to change the port

**Browser doesn't open** - Navigate to `http://127.0.0.1:8080/` manually

**Provider shows unverified** - Set the environment variable referenced in the provider record and re-verify

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