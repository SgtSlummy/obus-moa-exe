# Push & Active Jobs Report — 2026-09-06 19:35 UTC (cycle #456, final)

## Push Results

### All Pushed This Cycle
| Repo | Branch | Head | Result |
|------|--------|------|--------|
| obus-moa-exe | master | `03a5777` | ✅ Pushed (cron report 0456) |
| Davy Jones / Projects | main | `e5c3345` | ✅ Pushed (operator game launch, member profiles, admin web, tests) |

### Already In Sync (verified by push_and_list.sh)
| Repo | Branch | Head | Status |
|------|--------|------|--------|
| obus-moa-exe | codex/autonomy-context-agents | `ab02750` | ✅ In sync |
| mythos-router-source | main | `032e0c2` | ✅ In sync |
| temporal | main | `561ba4ee4` | ✅ In sync |
| hermes-photon-client | master | `d7acf11` | ✅ In sync |
| hermes-photon-server | master | `9cf3bd5` | ✅ In sync |
| warden | main | `6c7b2e9` | ✅ In sync |
| warden-discord-bot | main | `4fa686e` | ✅ In sync |
| Tarot-Router | main | (clean) | ✅ In sync |

### Blocked (pre-existing auth failures — no action possible)
| Repo | Branch | Remote | Error |
|------|--------|--------|-------|
| mempalace | develop | SgtSlummy/mempalace | 403 — not a collaborator |
| MoA-source | main | togethercomputer/MoA | 403 — not a collaborator |
| models-dev-source | dev | github.com:SgtSlummy/models.dev | SSH auth failure |
| warden-source | main | wardenenv/warden | 403 — not a collaborator |
| awesome-free-llm-apis-mnfst-source | main | mnfst/awesome-free-llm-apis | 403 — not a collaborator |
| awesome-free-models-source | main | 12britz/awesome-free-models | 403 — not a collaborator |
| awesome-freellm-apis-source | main | open-free-llm-api/awesome-freellm-apis | 403 — not a collaborator |
| free-ai-coding-source | main | inmve/free-ai-coding | 403 — not a collaborator |
| free-coding-models-source | main | vava-nessa/free-coding-models | 403 — not a collaborator |

## Uncommitted Changes (not pushed — left as-is)
| Dir | Branch | Changes |
|-----|--------|---------|
| obus-moa-exe | master | `M backend/game_runtime.py` (1 file modified) |
| DavyJonesBot/workspace | main | `?? .candidate-evidence-inspect/` (untracked dir with SLSA provenance) |
| Projects/Archives/obus-moa-exe-from-OneDrive | codex/recover-autonomy-context-agents-20260827 | Uncommitted changes + untracked node_modules/.bin/* and .codex/handoffs/, .pytest-tmp/ |
| Projects/Operator Special Forces Dungeon and Dragons | HEAD | Uncommitted changes |
| DavyJonesBot/workspace | main | `?? .candidate-evidence-inspect/` (untracked) |

## Active Background Processes (significant)

### Agent/LLM Runtimes
| Process | PID | MEM | Notes |
|---------|-----|-----|-------|
| **codex.exe** | 28048 | 487 MB | Active Codex agent |
| **llama-server.exe** | 16832 | 1.57 GB | Ollama local LLM server |
| **gortex.exe** | multiple | 62–637 MB | Graph/index workers (9 instances) |
| **mempalace-mcp.exe** | multiple | 5 MB | MemPalace MCP (7 instances) |
| **python.exe** | multiple | 12–576 MB | Agent workers, MCP bridges (20+ instances) |
| **node.exe** | multiple | 10–274 MB | Codex host, web UIs, MCP (15+ instances) |
| **OBus.exe / Obus.exe** | 7956, 19272, 20840 | 1.5–39 MB | Multiple OBus instances |
| **EchoWarp.exe** | 20072 | 93 MB | Warp sync client |
| **ChatGPT.exe** | multiple | 9–488 MB | 10 instances (user + agent) |

### Other Notable
- **pinchtab-windows-amd64.exe** (2 instances, 70 MB) — browser automation
- **chrome.exe** (8 instances, 4–37 MB)
- **msedgewebview2.exe** (10+ instances)
- **PowerToys** suite (FancyZones, AlwaysOnTop, ColorPicker, Peek, Awake — 5 processes)
- **OneDrive.Sync.Service.exe** — file sync active
- **tailscaled.exe** (2 instances) — Tailscale VPN

## Build / AUI Status
- **Latest build:** `build-aui-loop76/` (Aug 25) — **STALLED ~12 days**
- **Latest dist:** `dist-aui-loop76/` — matches build
- **No new build loops** since loop76. No EXE or installer progress.
- **Active builders:** None detected (no compile/build processes running)

## Submodules (all clean, detached HEADs)
| Submodule | Path | Commit |
|-----------|------|--------|
| Understand-Anything | `Understand-Anything/` | `99e62b7` |
| warpdotdev-warp | `third_party/warpdotdev-warp/` | `8c2cc73` |
| warp | `warp/` | `3504ce5` |

## Summary
- **2 repos pushed** this cycle (obus-moa-exe cron report, Davy Jones operator work)
- **8 repos** already in sync
- **9 repos** blocked by 403/SSH (pre-existing, no action possible)
- **4 dirs** have uncommitted changes — not pushed (not part of the push scope or intentionally left)
- **Active agents:** Codex (PID 28048), llama-server (PID 16832), gortex workers, mempalace MCP, multiple python/node worker pools
- **Build pipeline:** Still stalled at loop76 (~12 days)
- **System is active** with many agent/LLM processes consuming significant memory (llama-server 1.57 GB alone)

## Previous Cycle (#455, 06:34 UTC)
- 8/18 repos pushed clean, 10 blocked
- No active builder/agent jobs detected at that time
- This cycle: active Codex and llama-server processes now present
