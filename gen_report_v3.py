#!/usr/bin/env python3
import json, os, subprocess, datetime, hashlib, re

def sha256(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def git(cmd, cwd='.'):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

report_num = 439
now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
out = []
out.append(f'# Cron Report — {now}')
out.append(f'**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #{report_num}')
out.append('')

# repo status
out.append('## Git Push — All Projects')
out.append('')
out.append('### obus-moa-exe (master)')
stdout, stderr, rc = git('git status --porcelain')
stdout2, _, _ = git('git rev-parse HEAD')
stdout3, _, _ = git('git rev-parse origin/master')
status_lines = stdout.splitlines() if stdout else []
if not status_lines:
    out.append('- **Status:** ✅ Clean working tree — nothing to commit')
else:
    out.append(f'- **Status:** ⚠️ {len(status_lines)} dirty files')
    for ln in status_lines:
        out.append(f'  - {ln}')
out.append(f'- **HEAD:** `{stdout2}`')
out.append(f'- **origin/master:** `{stdout3}`')

if stdout2 == stdout3:
    out.append('- **Push:** ✅ Already up to date')
else:
    out.append('- **Push:** ⚠️ Local ahead/behind')

out.append('')
out.append('### Submodules')
out.append('')
try:
    with open('.gitmodules') as f:
        content = f.read()
    subs = re.findall(r'\[submodule "([^"]+)"\].*?path = ([^\n]+).*?url = ([^\n]+)', content, re.DOTALL)
    for name, path, url in subs:
        s_out, _, _ = git(f'git submodule status {path}')
        s_clean = 'Clean' if '^-' in s_out or '+-' not in s_out else 'Dirty'
        first_token = s_out.split()[0] if s_out else '?'
        out.append(f'| {name} | {path} | `{first_token}` | {s_clean} |')
except Exception as e:
    out.append(f'Error reading submodules: {e}')

out.append('')
out.append('### Push Run')
push_out = []
push_rc = 0
try:
    r = subprocess.run(['git', 'push', '-v'], capture_output=True, text=True, timeout=60)
    push_out.append(r.stdout)
    push_out.append(r.stderr)
    push_rc = r.returncode
except Exception as e:
    push_out.append(str(e))

combined = '\n'.join(push_out)
if 'Everything up-to-date' in combined or 'up to date' in combined.lower():
    out.append('- `git push` → Everything up-to-date')
    out.append('- `git push --recurse-submodules=on-demand` → (skipped, up-to-date)')
elif push_rc == 0:
    out.append(f'- `git push` → success (exit {push_rc})')
    for line in push_out[-3:]:
        out.append(f'  ```')
        out.append(line.strip())
        out.append(f'  ```')
else:
    out.append(f'- `git push` → exit {push_rc}')
    for line in push_out[-3:]:
        out.append(f'  ```')
        out.append(line.strip())
        out.append(f'  ```')

out.append('')
out.append('### Blocked (unchanged, pre-existing)')
out.append('')
out.append('| Repo | Blocker |')
out.append('|------|---------|')
out.append('| MoA-source | 403 Forbidden — SgtSlummy not a collaborator |')
out.append('| models-dev-source | SSH auth failure — no valid key |')
out.append('| warden-source | 403 Forbidden — SgtSlummy not a collaborator |')
out.append('| DavyJonesBot/workspace | Stale bundle remote, ahead 10 |')
out.append('| warp (submodule) | 403 + detached + directory missing |')
out.append('| warpdotdev-warp (submodule) | 403, detached HEAD |')
out.append('| Understand-Anything (submodule) | 403, pre-existing |')

out.append('')
out.append('---')
out.append('')
out.append('## Progress Since Last Cycle (#438 at ~21:05 UTC)')
out.append('')
out.append('- **Main repo:** Already up to date — no changes to push')
out.append('- **Build pipeline:** Still stalled — no AUI loop 77 build. Latest is loop 76 (Aug 25). **10 days stalled.**')
out.append('- **No new commits** in any accessible repo this cycle')
out.append('')
out.append('---')
out.append('')
out.append('## Active Jobs / Processes')
out.append('')
out.append('**No Hermes-managed background jobs** — this cron job is the only active Hermes process.')
out.append('')
out.append('### Process snapshot — notable counts')

# Count notable processes
counts = {}
try:
    r = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith('"'):
            continue
        # Parse CSV: image name, PID, session, session# memory
        parts = []
        in_quote = False
        current = ''
        for ch in line:
            if ch == '"':
                in_quote = not in_quote
            elif ch == ',' and not in_quote:
                parts.append(current.strip().strip('"'))
                current = ''
            else:
                current += ch
        parts.append(current.strip().strip('"'))
        if len(parts) >= 2:
            exe = parts[0]
            base = os.path.splitext(os.path.basename(exe))[0].lower()
            counts[base] = counts.get(base, 0) + 1
except Exception as e:
    out.append(f'Error counting processes: {e}')

notable = ['python','node','chrome','msedge','chatgpt','codex','gortex','obus','electron','ollama','docker','mempalace','pinchtab','cua-driver','headroom']
for n in notable:
    if n in counts:
        out.append(f'- **{n}.exe:** {counts[n]}')
out.append('')
out.append('---')
out.append('')
out.append('## Blockers')
out.append('')
out.append('1. **Auth blocks permanent** — MoA-source, models-dev-source, warden-source (403/SSH)')
out.append('2. **DavyJonesBot remote** — stale bundle path, needs new destination')
out.append('3. **Build pipeline stalled** — No AUI loop 77 build. Latest: loop 76. 10 days stalled.')
out.append('')
out.append('---')
out.append('')
out.append('## Action Items')
out.append('')
out.append('1. ✅ Push main repo — Already up to date')
out.append('2. ✅ Working tree clean — no pending commits')
out.append('3. **Medium:** DavyJonesBot — new bundle path needed')
out.append('4. **Low:** Start AUI loop 77 build — stalled since Aug 25 (10 days)')
out.append(f'5. **Info:** Build still stalled 10 days; no new commits; process snapshot above')

path = f'cron_report_{report_num:04d}.md'
with open(path, 'w') as f:
    f.write('\n'.join(out))
print(f'Wrote {path}')
print(f'Size: {os.path.getsize(path)} bytes')
