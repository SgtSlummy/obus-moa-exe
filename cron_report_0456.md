# Push Status — 2026-09-06 21:21 UTC (cron #456)

## Scan Scope
All git repositories under `/c/Users/Hermes/Documents/` (the location the temp push scripts target).

## Repositories Found: 3

### 1. obus-moa-exe
- Path: `/c/Users/Hermes/Documents/obus-moa-exe`
- Branch: `master` (tracked: `origin/master`)
- HEAD: `7f58554` — "Cron: push test_runtime.py warmup assertion fix"
- Status: **clean, nothing to commit**
- Push: ✅ Everything up-to-date
- Note: The 0449→HEAD delta reported by `check_continue.sh` is a phantom — the commit referenced (de9884a) no longer exists locally. Local history ends at 7f58554. The push_status_new.txt from cycle #455 was stale.

### 2. Tarot-Router (occultbus)
- Path: `/c/Users/Hermes/Documents/Tarot-Router`
- Branch: `main` (tracked: `origin/main`)
- Remote: `https://github.com/SgtSlummy/occultbus.git`
- HEAD: `1e7b57b` — "chore: snapshot recent work"
- Status: **clean, nothing to commit**
- Push: ✅ Everything up-to-date

### 3. ComfyUI
- Path: `/c/Users/Hermes/Documents/comfy/ComfyUI`
- Branch: `master`
- HEAD: `e0439f1c` — "chore: cron cleanup deleted temp files"
- Status: **clean, nothing to commit**
- Push: ❌ 403 Forbidden — `comfyanonymous/ComfyUI.git` denied to SgtSlummy
- Note: Branch has diverged from origin/master (2 local vs 83 remote commits). No push possible without collaborator access. Pre-existing, not actionable.

## Repos Previously Listed in push_status_new.txt (cycle #455) — NOW ABSENT

The following were listed in the old report but do NOT exist under `/c/Users/Hermes/Documents/` anymore:

| Repo | Old Status |
|------|------------|
| DavyJonesBot/workspace | MISSING |
| mempalace | MISSING |
| MoA-source | MISSING |
| models-dev-source | MISSING |
| warden-source | MISSING |
| awesome-free-llm-apis-mnfst-source | MISSING |
| awesome-free-models-source | MISSING |
| awesome-freellm-apis-source | MISSING |
| free-ai-coding-source | MISSING |
| free-coding-models-source | MISSING |
| hermes-photon-client | MISSING |
| hermes-photon-server | MISSING |
| temporal | MISSING |
| warden | MISSING |
| warden-discord-bot | MISSING |

These either migrated, were deleted, or were never under Documents (the old report used submodule paths or stale state). No push action is possible for them.

## Build / AUI Status
- Latest build: `build-aui-loop76/` (Aug 25) — **STALLED ~12 days**
- Latest EXE: `dist-aui-loop76/OBus.exe` (70.8 MB, Aug 25)
- No new build loops since loop76.
- No active builders or agent jobs detected.

## Submodules in obus-moa-exe (unchanged since last cycle)
| Submodule | Path | HEAD | Status |
|-----------|------|------|--------|
| Understand-Anything | `Understand-Anything/` | `99e62b7` | Clean (detached) |
| warpdotdev-warp | `third_party/warpdotdev-warp/` | `8c2cc73` | Clean (detached) |
| warp | `warp/` | `3504ce5` | Clean (detached) |

## Verdict
All 2 accessible repos (obus-moa-exe + Tarot-Router/occultbus) pushed clean this cycle. ComfyUI is blocked 403 (pre-existing, not actionable). All 13 repos from the old push_status_new.txt are absent from the current Documents tree — the old report was stale/phantom state. Build remains stalled at loop76 with no active agent jobs.
