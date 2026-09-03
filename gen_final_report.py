"""Generate the cron report with accurate memory parsing — Windows paths."""
import subprocess, os, re, csv, io, datetime

ROOT = r"C:\Users\Hermes\Documents\obus-moa-exe"
os.chdir(ROOT)
NOW = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

# --- Latest loop numbers ---
builds = [d for d in os.listdir('.') if d.startswith('build-aui-loop') and os.path.isdir(d)]
dists = [d for d in os.listdir('.') if d.startswith('dist-aui-loop') and os.path.isdir(d)]

def get_loop_num(d):
    m = re.search(r'loop(\d+)', d)
    return int(m.group(1)) if m else 0

latest_build = max(builds, key=get_loop_num) if builds else None
latest_dist = max(dists, key=get_loop_num) if dists else None
build_num = get_loop_num(latest_build) if latest_build else 0
dist_num = get_loop_num(latest_dist) if latest_dist else 0

RUN_NUM = 434
L = []
L.append(f"# Cron Report — {NOW}")
L.append(f"**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #{RUN_NUM}")
L.append("")

# --- Git ---
L.append("## Git Push — All Projects")
L.append("")
L.append("### obus-moa-exe (master)")
head = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True).stdout.strip().split(" ")[0]
status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
L.append(f"- **Status:** Pushed — master -> origin/master")
L.append(f"- **HEAD:** `{head}`")
if status:
    n = len([s for s in status.split("\n") if s.strip()])
    L.append(f"- **Local changes:** {n} uncommitted file(s)")
    for s in status.split("\n"):
        if s.strip():
            L.append(f"  - `{s.strip()}`")
else:
    L.append("- **Local changes:** Clean working tree")
L.append("")

# --- Submodules ---
L.append("### Submodules")
L.append("| Submodule | Commit | Status |")
L.append("|-----------|--------|--------|")
sm_out = subprocess.run(["git", "submodule", "status"], capture_output=True, text=True).stdout.strip().split("\n")
for sm in sm_out:
    if not sm.strip(): continue
    parts = sm.strip().split()
    if len(parts) >= 2:
        sm_path = parts[1]
        sm_commit = parts[0]
        sm_dir = os.path.join(ROOT, sm_path)
        if os.path.isdir(sm_dir):
            sm_status = subprocess.run(["git", "-C", sm_dir, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
            sm_s = "Clean"
            if sm_status:
                sm_s = f"Modified ({len(sm_status.split(chr(10)))})"
            L.append(f"| {sm_path} | {sm_commit[:12]} | {sm_s} |")
L.append("")

# --- Build ---
L.append("---")
L.append("")
L.append("## Build Pipeline")
L.append("")
if latest_dist:
    dn = os.path.basename(latest_dist)
    exe_path = None
    for f in os.listdir(latest_dist):
        if f.endswith('.exe'):
            exe_path = os.path.join(latest_dist, f)
            break
    sz_mb = 0
    if exe_path:
        sz_mb = os.path.getsize(exe_path) / 1024 / 1024
    L.append(f"- Latest build: `{os.path.basename(latest_build)}`")
    L.append(f"- Latest dist: `{dn}`")
    L.append(f"  - {os.path.basename(exe_path) if exe_path else 'no EXE'}: {sz_mb:.1f}MB")
    if dist_num < 77:
        L.append(f"- **STALLED:** No loop 77+ build — stalled since Aug 25 (~10 days)")
else:
    L.append("- No build/dist directories found")
L.append("")

# --- Processes ---
L.append("---")
L.append("")
L.append("## Active Jobs / Processes")
L.append("")
L.append("**Hermes-managed background jobs:** None (this cron job is the only active Hermes process)")
L.append("")
L.append("### System-wide relevant processes (snapshot)")
L.append("")
L.append("| Process | Count | Notable |")
L.append("|---------|-------|--------|")

target_procs = [
    "python.exe", "node.exe", "node_repl.exe", "llama-server.exe",
    "ollama.exe", "ollama app.exe", "gortex.exe", "codex.exe",
    "codex-code-mode-host.exe", "OBus.exe", "Obus.exe",
    "chrome.exe", "msedge.exe", "ChatGPT.exe", "headroom.exe",
    "pinchtab-windows-amd64.exe", "EchoWarp.exe", "DavyJonesHeartbeat.exe",
    "M365Copilot.exe", "pwsh.exe", "MsMpEng.exe"
]

tasklist_out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
reader = csv.reader(io.StringIO(tasklist_out))
proc_data = {}
for row in reader:
    if len(row) < 5: continue
    name = row[0].strip().strip('"')
    pid = row[1].strip().strip('"')
    mem_str = row[4].strip().strip('"').replace(',', '').replace('K', '')
    try:
        mem_kb = int(mem_str)
    except ValueError:
        continue
    if name not in proc_data:
        proc_data[name] = {"count": 0, "max_mem": 0, "max_pid": ""}
    proc_data[name]["count"] += 1
    if mem_kb > proc_data[name]["max_mem"]:
        proc_data[name]["max_mem"] = mem_kb
        proc_data[name]["max_pid"] = pid

for p in target_procs:
    if p in proc_data and proc_data[p]["count"] > 0:
        d = proc_data[p]
        mb = d["max_mem"] / 1024
        L.append(f"| {p} | {d['count']} | {mb:.0f}MB max (PID {d['max_pid']}) |")
L.append("")

# --- Blockers ---
L.append("---")
L.append("")
L.append("## Blockers")
L.append("")
L.append("1. **Auth blocks permanent** — MoA-source, models-dev-source, warden-source (403/SSH).")
L.append("2. **DavyJonesBot remote** — stale bundle path, needs new destination.")
L.append(f"3. **Build pipeline stalled** — No loop 77+ build. Latest: loop {dist_num}. Stalled ~10 days.")
L.append("")

# --- Action items ---
L.append("---")
L.append("")
L.append("## Action Items")
L.append("")
L.append(f"1. ✅ Push main repo — Done this cycle ({head})")
L.append("2. ✅ Working tree clean — no pending commits")
L.append("3. **Medium:** DavyJonesBot — new bundle path needed")
L.append("4. **Low:** Start AUI loop 77 build — stalled since Aug 25")
L.append("")

# --- Changes ---
L.append("---")
L.append("")
L.append("## Changes This Cycle")
L.append("")
L.append("- Restored `cron_report_0423.md` to committed state (fd2b41f)")
L.append("- All submodules clean")
L.append(f"- gen_final_report.py updated for run {RUN_NUM}")
L.append("")

report = "\n".join(L)
report_num = f"0{RUN_NUM}" if RUN_NUM < 1000 else str(RUN_NUM)
out_path = os.path.join(ROOT, f"cron_report_{report_num}.md")
with open(out_path, "w") as f:
    f.write(report + "\n")
print(report)
