# Cron Report 0365 — 2026-08-28 05:20 UTC

**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Model:** upstage/solar-pro4:free

## Push Results

| Repo | Branch | Commit | Result |
|------|--------|--------|--------|
| obus-moa-exe | master | `13c2ade` | ✅ **Pushed** — `aa6d99b..13c2ade` to origin |
| warp (submodule) | main | `dd76273` | ⚠️ **Clean** — detached at v1.4.0-3532, no push needed; 403 persists |
| warpdotdev-warp (submodule) | — | detached HEAD | ⚠️ **Clean** — 403 persists |
| Understand-Anything (submodule) | main | — | ⚠️ **Clean** — 403 persists |

## Active Processes

- uvicorn.exe (PID 1016) — OBus MOA backend on :8000
- DavyJonesHeartbeat.exe (PID 8836) — :3000 listener
- ollama.exe + ollama app.exe — present
- gortex.exe — multiple instances
- msedgewebview2.exe — multiple instances
- OBus.exe instances (multiple) — running
- llama-server.exe — present
- codex.exe — Codex agent

## Services

| Port | Status | Notes |
|------|--------|-------|
| `:8000` | ✅ UP | OBus MOA FastAPI — HTTP 200 |
| `:3000` | ✅ UP | Davy Jones — HTTP 200 |

Both services respond to `curl http://localhost:<port>/` with valid HTML.

## Committed Work (this cycle)

- `13c2ade` chore: refresh push and active job status reports for 05:10 cycle
- `15b7704` feat: add OBus URL resolution from startup receipts and probe body summarization

### OBus URL Resolution (`15b7704`)

New functionality added to the benchmark plan script:

- **`startup_receipt_obus_url()`** — reads `OBus/logs/startup/obus-startup-*.json` receipts, prefers the newest valid port (skips ports > 65535), returns `http://127.0.0.1:<port>` or `None`
- **`resolve_obus_url()`** — explicit URL passed as argument takes priority over startup receipt discovery
- **`summarize_probe_body()`** — strips secrets from probe responses, keeping only operational fields (card count, selected model, autonomy level, voice readiness, warm status, Ollama model list without secrets)

## Uncommitted Changes (preserved)

- `tests/test_benchmark_startup_receipt.py` — new test file (2.2K), not yet committed
  - Tests `startup_receipt_obus_url()` prefers newest valid loopback port
  - Tests invalid port (>65535) is skipped
  - Tests explicit URL wins over receipt discovery
  - Tests `summarize_probe_body()` excludes secrets from dashboard and keeps readiness fields
  - Tests `summarize_probe_body()` keeps only operational Ollama model fields

## Submodule Blockers (unchanged since last cycle)

| Submodule | Remote | Issue |
|-----------|--------|-------|
| warp | nvidia/warp | 403 Forbidden — not a collaborator; local clean |
| warpdotdev-warp | warpdotdev/warp | detached HEAD + 403 |
| Understand-Anything | Egonex-AI | 403 — not a collaborator |

## Build Pipeline

- **Status:** idle — no new EXEs since Aug 25 04:49
- **Latest commit:** `13c2ade` (05:10 UTC)

## Notes

- New OBus URL resolution from startup receipts provides a reliable way to discover the running OBus desktop app's HTTP endpoint without hardcoding ports
- Probe body summarization strips sensitive fields before logging/reporting, keeping only operational metadata
- One uncommitted test file (`test_benchmark_startup_receipt.py`) preserves coverage for the new URL resolution and probe summarization functions — ready for next commit cycle
- Submodule push failures remain unchanged — all are permission/collaborator issues, not transient errors
