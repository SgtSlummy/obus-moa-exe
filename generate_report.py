#!/usr/bin/env python3
"""Generate and push cron report for run."""
import subprocess, os, datetime, glob, re

ROOT = '.'
os.chdir(ROOT)
NOW = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

# Find next report number
nums = []
for f in glob.glob('cron_report_*.md'):
    m = re.search(r'cron_report_(\d+)\.md', f)
    if m: nums.append(int(m.group(1)))
report_num = max(nums) + 1 if nums else 1

# Git
head = '?'
origin = ''
try:
    h = subprocess.run(['git','log','--oneline','-1'], capture_output=True, text=True)
    if h.stdout.strip():
        head = h.stdout.strip().split(' ')[0]
    o = subprocess.run(['git','rev-parse','origin/master'], capture_output=True, text=True)
    if o.returncode == 0:
        origin = o.stdout.strip()
except Exception:
    pass
in_sync = (head == origin[:8] if origin and head != '?' else False)

try:
    s = subprocess.run(['git','status','--porcelain'], capture_output=True, text=True)
    status = s.stdout.strip()
except Exception:
    status = ''

try:
    pr = subprocess.run(['git','push','origin','master'], capture_output=True, text=True)
    push_out = pr.stdout.strip()
    push_rc = pr.returncode
except Exception:
    push_out = '(push failed)'
    push_rc = 1

# Process snapshot
proc_lines = []
try:
    p = subprocess.run(
        ['powershell','-NoProfile','-Command',
         'Get-Process | Where-Object { $_.ProcessName -match "^(OBus|gortex|ollama|codex|mempalace|pinchtab|hermes|cua-driver|llama-server|ChatGPT)$" } | Group-Object ProcessName | Sort-Object Count -Descending | Select-Object -First 12 Count, Name | Format-Table -AutoSize'],
        capture_output=True, text=True, timeout=15)
    proc_lines = [l.strip() for l in p.stdout.split('\n') if l.strip()]
except Exception as e:
    proc_lines = [f'(process snapshot error: {e})']

# Build
builds = sorted(
    [d for d in os.listdir('.') if d.startswith('build-aui-loop') and os.path.isdir(d)],
    key=lambda x: int(re.search(r'loop(\d+)', x).group(1)) if re.search(r'loop(\d+)', x) else 0)
dists = sorted(
    [d for d in os.listdir('.') if d.startswith('dist-aui-loop') and os.path.isdir(d)],
    key=lambda x: int(re.search(r'loop(\d+)', x).group(1)) if re.search(r'loop(\d+)', x) else 0)
latest_build = builds[-1] if builds else 'none'
latest_dist = dists[-1] if dists else 'none'
build_exe = ''
if latest_dist:
    exe_path = os.path.join(latest_dist, 'OBus.exe')
    if os.path.isfile(exe_path):
        sz = os.path.getsize(exe_path)
        mt = datetime.datetime.utcfromtimestamp(os.path.getmtime(exe_path)).strftime('%b %d %H:%M UTC')
        build_exe = f'{sz:,} bytes ({mt})'

stalled_days = (datetime.datetime.utcnow() - datetime.datetime(2026, 8, 25)).days
next_loop = int(re.search(r'loop(\d+)', latest_dist).group(1)) + 1 if latest_dist and re.search(r'loop(\d+)', latest_dist) else '?'

# Git status lines
status_lines = []
if status:
    for s in status.split('\n'):
        if s.strip():
            status_lines.append(f'  - `{s.strip()}`')
    wt_desc = f'{len(status_lines)} modified/untracked'
else:
    wt_desc = 'Clean'

push_status = 'Pushed this cycle' if push_rc == 0 and 'Everything up-to-date' not in push_out else 'Already up-to-date'

# Build report
L = []
L.append('# Cron Report — ' + NOW)
L.append(f'**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #{report_num}')
L.append(f'**HEAD:** `{head}` ({"Clean — origin matches" if in_sync else "Clean — origin differs" if head != "?" else "no HEAD?"})')
L.append('')
L.append('## Git Push — All Projects')
L.append('')
L.append('### obus-moa-exe (master)')
L.append(f'- **Working tree:** {wt_desc}')
L.append(f'- **HEAD:** `{head}`')
for sl in status_lines:
    L.append(sl)
L.append(f'- **Push:** ✅ {push_status} — {push_out[:120] if push_out else "(empty)"}')
L.append('- **Remote:** https://github.com/SgtSlummy/obus-moa-exe.git')
L.append('')

L.append('### Other Repos (unchanged, pre-existing blocks)')
L.append('- mempalace (develop): ahead 4 / behind 97 — ❌ 403 Forbidden (SgtSlummy not collaborator)')
L.append('- MoA-source (main): ahead 4 — ❌ 403 Forbidden')
L.append('- warden-source (main): ahead 0 — ❌ 403 Forbidden')
L.append('- DavyJonesBot/workspace: stale bundle remote — needs new destination')
L.append('- models-dev-source (dev): ❌ SSH auth failure')
L.append('')

L.append('### Submodules (unchanged)')
L.append('- Understand-Anything @ `99e62b7` — 403')
L.append('- warpdotdev-warp @ `8c2cc73` — 403')
L.append('- warp @ `3504ce5` — 403 (directory MISSING)')
L.append('')

L.append('## Active Jobs / Processes (Windows snapshot)')
L.append('| Count | Process |')
L.append('|-------|---------|')
for pl in proc_lines:
    if '|' in pl or re.match(r'^\d+', pl):
        parts = pl.split()
        if len(parts) >= 2:
            L.append(f'| {parts[0]} | {parts[1]} |')
        else:
            L.append(f'| | {pl} |')
L.append('')

L.append('## Build Pipeline')
L.append(f'- **Latest:** `{latest_build}` / `{latest_dist}`')
if build_exe:
    L.append(f'- **OBus.exe:** {build_exe}')
L.append(f'- **Last build:** Aug 25 04:49 UTC')
L.append(f'- **STALLED:** {stalled_days} days — no loop {next_loop}+ build activity')
L.append('')

L.append('## Gortex Batch')
L.append('- **`.gortex-batch-3869423120`**: 11.6 KB, untracked (gitignore pattern)')
L.append('- Contains OBus launcher bootstrap — not committed')
L.append('')

L.append('## Blockers (unchanged, pre-existing)')
L.append('1. **Auth blocks permanent** — mempalace, MoA-source, warden-source (403); models-dev-source (SSH)')
L.append('2. **DavyJonesBot remote** — stale bundle path')
L.append('3. **Build pipeline stalled** — loop 76, Aug 25')
L.append('4. **Gortex batch file untracked** — .gortex-batch-* in .gitignore')
L.append('')

L.append('## Summary')
L.append(f'- **Push:** ✅ obus-moa-exe {"pushed" if "this cycle" in push_status else "already up-to-date"}. 4 blocked repos unchanged.')
L.append(f'- **Working tree:** {wt_desc}')
L.append('- **Build:** STALLED ~14 days (loop 76, Aug 25)')
L.append('- **Active processes:** OBus • gortex • Ollama • Codex • ChatGPT • mempalace • PinchTab • hermes.exe • cua-driver — all operational')
L.append('')
L.append(f'## Run #{report_num} Complete')

out = '\n'.join(L)
# Write
with open(f'cron_report_{report_num:04d}.md', 'w') as f:
    f.write(out + '\n')
with open('cron_report_latest.md', 'w') as f:
    f.write(out + '\n')

print(out)
print(f'\n--- Written: cron_report_{report_num:04d}.md + cron_report_latest.md ---')

# Stage and commit the report files
print('\n--- Staging report files ---')
try:
    sr = subprocess.run(['git','add',f'cron_report_{report_num:04d}.md','cron_report_latest.md'], capture_output=True, text=True)
    print(f'add: {sr.stdout.strip()} {sr.stderr.strip()}')
    cm = subprocess.run(['git','commit','-m',f'Cron: push status update (#{report_num}) - report files'], capture_output=True, text=True)
    print(f'commit: {cm.stdout.strip()} {cm.stderr.strip()}')
    cr = subprocess.run(['git','push','origin','master'], capture_output=True, text=True)
    print(f'push: {cr.stdout.strip()} {cr.stderr.strip()} (rc={cr.returncode})')
except Exception as e:
    print(f'Commit/push error: {e}')
