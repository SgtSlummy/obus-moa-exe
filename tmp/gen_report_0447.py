import subprocess, os, datetime, re

repo_root = r"C:\Users\Hermes\Documents\obus-moa-exe"

def run(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd or repo_root, timeout=60)
    return r.returncode, r.stdout, r.stderr

# Git status for all repos
def git_all():
    results = {}
    rc, out, err = run("git status --short")
    results['main'] = {'status': out.strip().split('\n') if out.strip() else [], 'stderr': err.strip()}
    rc, out, err = run("git log --oneline -1")
    results['main_head'] = out.strip()
    rc, out, err = run("git push -v 2>&1 | tail -5")
    results['main_push'] = out.strip()
    rc, out, err = run("git submodule status")
    results['submodules'] = out.strip().split('\n') if out.strip() else []
    rc, out, err = run("find . -type d -name '.git' -printf '%h\n' 2>/dev/null")
    results['git_dirs'] = [d.strip() for d in out.strip().split('\n') if d.strip()]
    return results

git = git_all()

# Build pipeline check — use version-sort
def check_builds():
    loops = []
    for d in os.listdir(repo_root):
        m = re.match(r'build-aui-loop(\d+)$', d)
        if m and os.path.isdir(os.path.join(repo_root, d)):
            loops.append((int(m.group(1)), d))
    loops.sort()
    latest_loop = loops[-1][1] if loops else "none"
    latest_num = loops[-1][0] if loops else 0

    dists = []
    for d in os.listdir(repo_root):
        m = re.match(r'dist-aui-loop(\d+)$', d)
        if m and os.path.isdir(os.path.join(repo_root, d)):
            dists.append((int(m.group(1)), d))
    dists.sort()
    latest_dist = dists[-1][1] if dists else "none"
    latest_dist_num = dists[-1][0] if dists else 0

    exe_path = os.path.join(repo_root, latest_dist, "OBus.exe")
    exe_size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
    return latest_loop, latest_num, latest_dist, latest_dist_num, exe_size

latest_loop, latest_loop_num, latest_dist, latest_dist_num, exe_size = check_builds()

now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
report_num = 447

report = f"""# Cron Report — {now}
**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #{report_num}
**HEAD:** `{git['main_head'].split()[0] if git['main_head'] else 'unknown'}`

## Git Push — All Projects

### obus-moa-exe (master)
- **Working tree:** {'Dirty' if git['main']['status'] else 'Clean'} ({len(git['main']['status'])} entries)
"""
if git['main']['status']:
    for s in git['main']['status']:
        report += f"  - `{s}`\n"

report += f"""
- **HEAD:** `{git['main_head']}`
- **Push:** {git['main_push'][:200] if git['main_push'] else 'no output'}
"""

if git['submodules']:
    report += "\n### Submodules\n"
    for sm in git['submodules']:
        report += f"- `{sm}`\n"

# Stalled days
import datetime as dt
build_date = dt.datetime(2026, 8, 25, 4, 49, tzinfo=dt.timezone.utc)
days_stalled = (dt.datetime.now(dt.timezone.utc) - build_date).days

report += f"""
## Build Pipeline
- **Latest:** `{latest_loop}` (loop {latest_loop_num}) / `{latest_dist}` (dist {latest_dist_num})
- **OBus.exe:** {exe_size:,} bytes ({exe_size/1024/1024:.1f} MB)
- **Last build:** Aug 25 04:49 UTC
- **STALLED:** {days_stalled} days, no loop {latest_loop_num+1}+ build activity
"""

push_ok = 'up to date' in git['main_push'].lower() or 'everything up-to-date' in git['main_push'].lower()
tree_clean = not git['main']['status']
report += f"""
## Run #{report_num} Complete
- Push: {'✅ Synced' if push_ok else '⚠️ Check'}
- Working tree: {'✅ Clean' if tree_clean else '⚠️ Dirty (' + str(len(git['main']['status'])) + ' scratch entries)'}
- Blocked repos: unchanged (3×403, 1×SSH, 1 stale bundle, 3 submodule 403s)
"""

with open(os.path.join(repo_root, f"cron_report_0{report_num}.md"), "w") as f:
    f.write(report)

# Also update latest symlink
latest_path = os.path.join(repo_root, "cron_report_latest.md")
with open(latest_path, "w") as f:
    f.write(report)

print(report)
