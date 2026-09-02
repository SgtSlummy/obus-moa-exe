# Cron Job: Active Jobs Check

**Job ID:** 893c7df0ef71
**Run Time:** 2026-09-02 16:36:56
**Schedule:** every 10m

## Push Summary

### Committed & Pushed
- Committed: `17b1275` — "Cron: snapshot push output and add A23 external verifier handoff brief"
- Pushed to origin/master: ✅

### Pending Changes (now committed)
- `push_output.txt` — refreshed process listing (393 insertions, 354 deletions)
- `docs/A23_EXTERNAL_VERIFIER_HANDOFF.md` — new A23 external evaluator handoff brief

### Pre-existing Push Blocks (unchanged)
- **403 Forbidden**: mempalace (develop, ahead 1), MoA-source (main, ahead 4), warden-source (main, ahead 1) — SgtSlummy not a collaborator
- **SSH failure**: models-dev-source (dev, ahead 1) — no valid SSH key
- **Stale bundle**: DavyJonesBot/workspace (main, ahead 10) — needs new remote destination; new `.candidate-evidence-inspect/` dir with verified SLSA attestations
- **No worktree**: Tarot-Router — HEAD unknown

### Submodules (unchanged, pre-existing 403)
- third_party/warpdotdev-warp, warp, Understand-Anything — all 403 (no write access)

## Active Jobs / Running Processes

### Services
| Service | PID | Status | Notes |
|---------|-----|--------|-------|
| uvicorn (OBus MOA FastAPI) | — | ✅ UP :8000 | Health check returns 200 |
| DavyJonesHeartbeat | 3740 | ✅ UP :3000 | Discord bot heartbeat (42MB) |

### LLM / Inference
| Process | PID | Memory | Notes |
|---------|-----|--------|-------|
| llama-server.exe | 9440 | 3.26GB | Local LLM inference server — largest single process |
| python.exe (large) | 31852, 22032 | 500-509MB each | Likely LLM-related Python workers |

### Graph / Memory
| Process | Instances | Memory range | Notes |
|---------|-----------|--------------|-------|
| gortex.exe | 9 instances | 14MB–539MB | Graph analysis; largest PID 22308 at 539MB (stable) |
| mempalace-mcp.exe | 7 instances | 4.7–5.0MB each | Memory palace MCP servers |

### Codex
| Process | PID | Memory | Notes |
|---------|-----|--------|-------|
| codex.exe | 30612 | 627MB | Codex agent — large, active |
| codex-code-mode-host.exe | 17500 | 20MB | Codex host |
| codex.exe | 29864 | 50MB | Secondary codex instance |

### OBus Desktop
| Count | Memory range | Notes |
|-------|--------------|-------|
| 11 instances | 1.2MB–102MB | Desktop app instances; largest PID 14016 at 102MB |

### Browser Automation
| Process | Instances | Memory range | Notes |
|---------|-----------|--------------|-------|
| pinchtab-windows-amd64.exe | 3 instances | 69–71MB each | Browser automation |
| msedge.exe | 7 instances | 12–175MB | Edge browser; largest PID 31460 at 175MB |
| msedgewebview2.exe | 18 instances | 1.9–49MB | WebView2 instances |

### Other Notable
- node.exe: 11 instances (2.9MB–274MB); largest PID 11924 at 274MB
- ChatGPT.exe: present (~1.09GB, stable)
- EchoWarp.exe: present (Warp runtime, 44MB)
- PowerToys suite: active (FancyZones, AlwaysOnTop, Awake, QuickAccess, Peek)

### Python Processes
- 53 python.exe instances total, mostly small (3–24MB); several medium (11–41MB); 2 large (500–509MB)

## Build Pipeline

- **Status**: STALLED since Aug 25
- **Latest build**: loop 76 (`dist-aui-loop76/OBus.exe`, 67.5MB, Aug 25 04:49 UTC)
- **No loop 77+**: Pipeline has not progressed in 8+ days
- **Scripts available**: `scripts/build_thor_deployment.py`, `scripts/build_thor_loki_pair.py` — Thor/Loki pair deployment builders exist but appear unused

## Codex Worktree

- **Path**: `C:/Users/Hermes/OBus-Thor-Loki-Paired/source-worktree`
- **Status**: DIRECTORY MISSING — no longer accessible
- **Last verified**: In sync at run #417 (Sep 1 07:44 UTC)
- **Branch**: `codex/autonomy-context-agents` (HEAD f8fa545)
- **Action needed**: Re-create or relocate worktree at accessible path if still needed

## Cron Report Cadence

- Reports generated regularly: 0341 through 0419
- Latest: `cron_report_0419.md` (Sep 2 11:17 UTC) — covers push check and active jobs
- Latest snapshot: `cron_report_latest.md` (mirror of 0419)

## Blockers Summary

1. **Build pipeline stalled** — No AUI loop 77+ in 8+ days; medium priority
2. **Codex worktree missing** — Directory gone; re-create if needed; medium priority
3. **DavyJonesBot remote** — Stale bundle; needs new destination or real remote; medium priority
4. **Auth blocks (permanent)** — mempalace, MoA-source, warden-source, models-dev-source all unreachable; no action possible

## No New Action Items This Cycle

All accessible repos pushed clean. Services are up. No new processes started or stopped significantly since last cycle. The A23 external verifier handoff brief was created and pushed — it documents the A23 qualification protocol for an independent evaluator but does not change Obus's current A2 status.
