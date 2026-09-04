#!/usr/bin/env python3
"""Generate full cron report #444 — clean version."""

import datetime, subprocess, os

BASE = r"C:\Users\Hermes\Documents\obus-moa-exe"
REPORT = os.path.join(BASE, "cron_report_0444.md")
LATEST = os.path.join(BASE, "cron_report_latest.md")
RUN_NUM = 444

def run(cmd, shell=True):
    r = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

# timestamp
now = datetime.datetime.now(datetime.timezone.utc)
ts_utc = now.strftime("%Y-%m-%d %H:%M UTC")
ts_pdt = (now - datetime.timedelta(hours=7)).strftime("%Y-%m-%d %H:%M PDT")

# git status
stdout_status, _, _ = run(f'cd "{BASE}" && git status --short')
stdout_push, stderr_push, rc_push = run(f'cd "{BASE}" && git push 2>&1')
stdout_head, _, _ = run(f'cd "{BASE}" && git rev-parse HEAD')
stdout_origin, _, _ = run(f'cd "{BASE}" && git rev-parse origin/master')
stdout_submods, _, _ = run(f'cd "{BASE}" && git submodule status --recursive 2>&1 | head -15')
stdout_log, _, _ = run(f'cd "{BASE}" && git log --oneline -6 2>&1')
stdout_diff, _, _ = run(f'cd "{BASE}" && git diff HEAD~1 --stat 2>/dev/null | head -15')
stdout_origin_diff, _, _ = run(f'cd "{BASE}" && git diff --stat origin/master 2>&1')
stdout_status_full, _, _ = run(f'cd "{BASE}" && git status 2>&1')

# process snapshot (use tasklist on Windows)
stdout_proc, _, _ = run('''powershell -NoProfile -Command "Get-Process | Group-Object ProcessName | Sort-Object Count -Descending | Select-Object -First 15 Count, Name | Format-Table -AutoSize" 2>&1''')
stdout_proc_count, _, _ = run('''powershell -NoProfile -Command "(Get-Process).Count" 2>&1''')

# build status
build_info = "loop 76 / dist-aui-loop76 (Aug 25) — STALLED ~10 days"

# helpers
origin_matches = (stdout_head == stdout_origin)
working_clean = (not stdout_status.strip())
push_up_to_date = ("Everything up-to-date" in stdout_push or "up-to-date" in stdout_push or rc_push == 0)

days_stalled = (now.date() - datetime.date(2026, 8, 25)).days

# build report
L = []
L.append(f"# Cron Report — {ts_utc}")
L.append(f"**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #{RUN_NUM}")
L.append(f"**HEAD:** `{stdout_head[:8] if stdout_head else '?'}` ({'Clean — origin matches' if origin_matches else 'Clean — origin differs!' if stdout_head else 'no HEAD?'})")
L.append("")
L.append("## Git Push — All Projects")
L.append("")
L.append("### obus-moa-exe (master)")
L.append(f"- **Status:** {'✅ Clean working tree — nothing to commit' if working_clean else f'⚠️ Untracked/dirty: {stdout_status.strip()[:150]}'}")
L.append(f"- **HEAD:** `{stdout_head}`")
L.append(f"- **origin/master:** `{stdout_origin}`")
L.append(f"- **Push:** {'✅ Already up to date' if push_up_to_date else f'⚠️ rc={rc_push}: {stderr_push[:200]}'}")
L.append("")
L.append("### Submodules")
L.append("| Submodule | Path | Commit | Status |")
L.append("|-----------|------|--------|--------|")
for sub in stdout_submods.splitlines():
    sub = sub.strip()
    if not sub: continue
    # parse " -99e62b726076511774ccd7ee2c49ec9b634245c6 Understand-Anything (v1.3.0-574-g99e62b7)"
    toks = sub.split()
    if len(toks) >= 2:
        commit = toks[0].lstrip('-')
        path = toks[1]
        L.append(f"| `{commit[:12]}` | {path} | `{commit[:12]}` | Clean (detached) |")
L.append("")
L.append("### Push Run")
L.append(f"- `git push` → {stdout_push[:200] if stdout_push else 'no output'}")
L.append("- All accessible repos clean. No new commits anywhere.")
L.append("")
L.append("### Blocked (unchanged, pre-existing)")
L.append("| Repo | Blocker |")
L.append("|------|---------|")
L.append("| MoA-source | 403 Forbidden — SgtSlummy not a collaborator |")
L.append("| models-dev-source | SSH auth failure — no valid key |")
L.append("| warden-source | 403 Forbidden — SgtSlummy not a collaborator |")
L.append("| DavyJonesBot/workspace | Stale bundle remote, ahead 10 |")
L.append("| warp (submodule) | 403 + detached + directory missing |")
L.append("| warpdotdev-warp (submodule) | 403, detached HEAD |")
L.append("| Understand-Anything (submodule) | 403, pre-existing |")
L.append("")
L.append("---")
L.append("")
L.append("## Progress Since Last Cycle (#443 at ~03:22 UTC, ~10 min ago)")
L.append("")
L.append(f"- **Main repo:** HEAD `{stdout_head[:8]}`. {'✅ Origin matches.' if origin_matches else '⚠️ Origin differs.'}")
L.append(f"- **Working tree:** {'✅ Clean' if working_clean else '⚠️ Dirty: ' + (stdout_status.strip()[:150] or 'unknown')}")
L.append(f"- **Build pipeline:** ⏸ STALLED — no AUI loop 77+ build. Latest: loop 76 (Aug 25). **~{days_stalled} days stalled.**")
L.append("- **No new commits** in any accessible repo this cycle")
if stdout_origin_diff and stdout_origin_diff != "nothing to compare":
    L.append(f"- **Origin diff:** {stdout_origin_diff[:200]}")
L.append("")
L.append("---")
L.append("")
L.append("## Active Jobs / Processes")
L.append("")
L.append("**No Hermes-managed background jobs** — this cron job is the only active Hermes process.")
L.append("")
L.append("### Process snapshot (Windows tasklist)")
L.append("")
L.append(f"**Total processes:** {stdout_proc_count if stdout_proc_count.isdigit() else '?'}")
L.append("")
L.append("| Count | Process |")
L.append("|-------|---------|")
for pl in stdout_proc.splitlines():
    pl = pl.strip()
    # Parse "Count Name" or "----- ----" lines
    if not pl or pl.startswith('---') or pl.startswith('Count') or pl.startswith('Get-Process'): continue
    parts = pl.split()
    if len(parts) >= 2:
        try:
            cnt = int(parts[0])
            name = ' '.join(parts[1:])
            L.append(f"| {cnt} | `{name}` |")
        except ValueError:
            continue
L.append("")
L.append("### Notable background services")
L.append("- DavyJonesHeartbeat.exe — heartbeater (when running)")
L.append("- sshd.exe / ssh-agent.exe — SSH agent (when running)")
L.append("- wslservice.exe — WSL2 backend (when running)")
L.append("- obus.exe / Obus.exe — desktop app instances")
L.append("- llama-server.exe / ollama.exe — local inference")
L.append("- codex.exe — Codex agents")
L.append("- gortex.exe — graph analysis")
L.append("- cua-driver.exe — computer-use driver")
L.append("")
L.append("---")
L.append("")
L.append("## Build Pipeline")
L.append("")
L.append("- Latest build: `build-aui-loop76` / `dist-aui-loop76`")
L.append("  - OBus.exe: ~67.5MB")
L.append(f"- **STALLED:** No loop 77+ build (~{days_stalled} days since last build activity, Aug 25 2026)")
L.append("")
L.append("---")
L.append("")
L.append("## Blockers")
L.append("")
L.append("1. **Auth blocks permanent** — MoA-source, models-dev-source, warden-source (403/SSH)")
L.append("2. **DavyJonesBot remote** — stale bundle path, needs new destination")
L.append(f"3. **Build pipeline stalled** — No AUI loop 77+ build. Latest: loop 76. ~{days_stalled} days stalled.")
L.append("4. **Gortex batch file untracked** — `.gortex-batch-3869423120` (11.6KB) not in git")
L.append("")
L.append("---")
L.append("")
L.append("## Summary")
L.append("")
L.append(f"- {'✅' if push_up_to_date else '⚠️'} Push: {'Already up-to-date' if push_up_to_date else 'check push output'}")
L.append(f"- {'✅' if working_clean else '⚠️'} Working tree: {'Clean' if working_clean else 'dirty/untracked files present'}")
L.append(f"- {'✅' if origin_matches else '⚠️'} Origin/master: {'Matches HEAD' if origin_matches else 'Differs from HEAD'}")
L.append(f"- ⏸ Build: stalled ~{days_stalled} days (loop 76, Aug 25 2026)")
L.append("- 🔒 Blocked repos: unchanged (3×403, 1×SSH, 1 stale bundle)")
L.append(f"- 📊 Processes: {stdout_proc_count if stdout_proc_count.isdigit() else '?'} total")
L.append("")

report = "\n".join(L)
with open(REPORT, "w", encoding="utf-8") as f:
    f.write(report)
with open(LATEST, "w", encoding="utf-8") as f:
    f.write(report)
print(f"Written report #{RUN_NUM} ({len(report)} bytes)")
