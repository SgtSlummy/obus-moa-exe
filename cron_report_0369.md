# Cron Report 0369 — 2026-08-28 07:51 UTC (finalized)

## Services — both healthy

| Port | Status | Process |
|------|--------|---------|
| :8000 | ✅ UP | uvicorn (PID 1016) — OBus MOA FastAPI |
| :3000 | ✅ UP | DavyJonesHeartbeat (PID 8836) |

## Git — main repo pushed, codex branch up to date

```
740ee33 chore: cron report 0368 and push status refresh  ← THIS RUN (also finalized 0369)
d2e1e59 chore: cron report 0366-0367 and push status refresh
b3733c8 chore: refresh warp submodule pointer for 05:57 cycle
2d731bc test: add OBus URL resolution and probe summarization coverage
cc9a190 chore: cron report 0365 — push verification and OBus URL resolution
```

- Working tree: clean
- **Push result (master)**: ✅ `740ee33` → origin/master (fast-forward, 1 commit)
- **Push result (codex/autonomy-context-agents)**: ✅ Up to date — no new commits since 09:13 cycle
- Remote HEAD: `740ee33` on master — matches local HEAD

### Submodule push status — unchanged (all 403)

| Submodule | State | Push |
|-----------|-------|------|
| warp (nvidia/warp) | `33530bd` — 4 commits behind main, detached | ❌ 403 (no write access) |
| warpdotdev-warp | `6afb6c8` — detached HEAD | ❌ 403 (no write access) |
| Understand-Anything | `99e62b7` — clean | ❌ 403 (no write access) |

All three remain 403-blocked. No new credential options available. Warp additionally has `sgtfork` remote pointing at deleted repo.

## Processes (OBus-relevant) — 64 running, unchanged

| Name | PIDs | Notes |
|------|------|-------|
| DavyJonesHeartbeat.exe | 8836 | :3000 listener |
| uvicorn.exe | 1016 | :8000 backend |
| OBus-6dd1e0e.exe | 4028, 21372 | OBus instances |
| OBus.exe / Obus.exe | 18 instances | Desktop app |
| codex.exe | 25524, 31284 | Codex agent |
| codex-code-mode-host.exe | 5984 | Codex host |
| gortex.exe | 4024, 16652, 17244, 17448 | Graph tools |
| llama-server.exe | 22292 | Local LLM (2.1 GB) |
| mempalace-mcp.exe | 20860 | Memory palace |
| ollama app.exe / ollama.exe | 35324, 34368 | Ollama service |
| python.exe | 26 instances | Various workers |

No processes died or new ones appeared vs 0367.

## New this cycle
- `cron_report_0368.md` written and pushed (report for 07:51 UTC run)
- `cron_report_0369.md` written and committed (this finalized report)
- `push_status.txt` refreshed

## Action taken
- ✅ Main repo master: pushed `740ee33` to origin/master
- ✅ codex/autonomy-context-agents: confirmed up to date (no push needed)
- ⛔ Submodules: not retried — all three remain 403-blocked
- ✅ Services: both confirmed UP

## Summary
All active worktree branches pushed and up to date. Services healthy. Submodules blocked by 403 (no write access to any remote). 64 OBus-relevant processes stable.
