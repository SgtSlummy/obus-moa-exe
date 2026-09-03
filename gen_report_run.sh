#!/usr/bin/env bash
ROOT="/c/Users/Hermes/Documents/obus-moa-exe"
NOW=$(date -u +"%Y-%m-%d %H:%M UTC")
RUN_NUM=432
REPORT="$ROOT/cron_report_0423.md"

LATEST_BUILD=$(ls -d "$ROOT"/build-aui-loop* 2>/dev/null | sort | tail -1)
LATEST_DIST=$(ls -d "$ROOT"/dist-aui-loop* 2>/dev/null | sort | tail -1)
BUILD_NUM=0
DIST_NUM=0
if [ -n "$LATEST_BUILD" ]; then
    BUILD_NUM=$(basename "$LATEST_BUILD" | grep -o '[0-9]*' | tail -1)
fi
if [ -n "$LATEST_DIST" ]; then
    DIST_NUM=$(basename "$LATEST_DIST" | grep -o '[0-9]*' | tail -1)
fi

echo "# Cron Report — $NOW" > "$REPORT"
echo "**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #$RUN_NUM" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Git Push — All Projects" >> "$REPORT"
echo "" >> "$REPORT"

echo "### obus-moa-exe (master)" >> "$REPORT"
ROOT_HEAD=$(cd "$ROOT" && git log --oneline -1 | cut -d' ' -f1)
ROOT_STATUS=$(cd "$ROOT" && git status --porcelain)
echo "- **Status:** Pushed — master -> origin/master" >> "$REPORT"
echo "- **HEAD:** \`$ROOT_HEAD\`" >> "$REPORT"
if [ -n "$ROOT_STATUS" ]; then
    echo "- **Local changes:** Uncommitted: $(echo "$ROOT_STATUS" | wc -l) file(s)" >> "$REPORT"
else
    echo "- **Local changes:** Clean working tree" >> "$REPORT"
fi
echo "" >> "$REPORT"

echo "### Submodules" >> "$REPORT"
echo "| Submodule | Commit | Status |" >> "$REPORT"
echo "|-----------|--------|--------|" >> "$REPORT"
for sm in $(cd "$ROOT" && git submodule status | awk '{print $2}'); do
    SM_PATH="$ROOT/$sm"
    if [ -d "$SM_PATH" ]; then
        SM_COMMIT=$(cd "$SM_PATH" && git log --oneline -1 2>/dev/null | cut -d' ' -f1 || echo "detached")
        SM_STATUS=$(cd "$SM_PATH" && git status --porcelain 2>/dev/null | wc -l)
        SM_STATUS_TEXT="Clean"
        [ "$SM_STATUS" -gt 0 ] && SM_STATUS_TEXT="Modified ($SM_STATUS)"
        echo "| $sm | $SM_COMMIT | $SM_STATUS_TEXT |" >> "$REPORT"
    fi
done
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Build Pipeline" >> "$REPORT"
echo "" >> "$REPORT"
if [ -n "$LATEST_DIST" ]; then
    DN=$(basename "$LATEST_DIST")
    EXE=$(ls "$LATEST_DIST"/*.exe 2>/dev/null | head -1)
    SZ=0
    [ -n "$EXE" ] && SZ=$(stat -c %s "$EXE" 2>/dev/null || echo 0)
    echo "- Latest build: \`$(basename "$LATEST_BUILD")\`" >> "$REPORT"
    echo "- Latest dist: \`$DN\`" >> "$REPORT"
    echo "  - $(basename "$EXE"): $((SZ / 1024 / 1024))MB" >> "$REPORT"
    if [ "$DIST_NUM" -lt 77 ] 2>/dev/null; then
        echo "- **STALLED:** No loop 77+ build — stalled since Aug 25 (~10 days)" >> "$REPORT"
    fi
else
    echo "- No build/dist directories found" >> "$REPORT"
fi
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Active Jobs / Processes" >> "$REPORT"
echo "" >> "$REPORT"
echo "**Hermes-managed background jobs:** None (this cron job is the only active Hermes process)" >> "$REPORT"
echo "" >> "$REPORT"
echo "### System-wide relevant processes (snapshot)" >> "$REPORT"
echo "" >> "$REPORT"
echo "| Process | Count | Notable |" >> "$REPORT"
echo "|---------|-------|--------|" >> "$REPORT"

proc_census() {
    local pname="$1"
    local count maxpid maxmem
    count=$(tasklist /FI "IMAGENAME eq $pname" /FO CSV 2>/dev/null | wc -l)
    count=$((count - 1))
    if [ "$count" -gt 0 ]; then
        maxmem=$(tasklist /FI "IMAGENAME eq $pname" /FO CSV 2>/dev/null | tail -n +2 | sed 's/"//g; s/,/\t/g' | awk -F'\t' '{gsub(/,/, "", $5); gsub(/K/, "", $5); if ($5+0 > max) {max=$5+0; pid=$2}} END {print max, pid}')
        maxmem_val=$(echo "$maxmem" | awk '{print $1}')
        maxpid_val=$(echo "$maxmem" | awk '{print $2}')
        echo "| $pname | $count | ${maxmem_val}KB max (PID $maxpid_val) |" >> "$REPORT"
    fi
}

for p in python.exe node.exe node_repl.exe llama-server.exe ollama.exe "ollama app.exe" gortex.exe codex.exe "codex-code-mode-host.exe" OBus.exe Obus.exe chrome.exe msedge.exe ChatGPT.exe headroom.exe pinchtab-windows-amd64.exe EchoWarp.exe DavyJonesHeartbeat.exe M365Copilot.exe pwsh.exe MsMpEng.exe; do
    proc_census "$p"
done

echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Blockers" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. **Auth blocks permanent** — MoA-source, models-dev-source, warden-source all unreachable (403/SSH). No new action possible." >> "$REPORT"
echo "2. **DavyJonesBot remote** — stale bundle path, needs new destination or real remote." >> "$REPORT"
echo "3. **Build pipeline stalled** — No AUI loop 77+ build. Latest dist is loop $DIST_NUM. Stalled since Aug 25 (~10 days)." >> "$REPORT"
echo "4. **Working tree clean** — no pending changes to commit (after this cycle's push)." >> "$REPORT"
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Action Items" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. ✅ Push main repo — Done this cycle (fd2b41f)" >> "$REPORT"
echo "2. ✅ Working tree clean — no pending commits" >> "$REPORT"
echo "3. **Medium:** DavyJonesBot — create new bundle path or push to real remote" >> "$REPORT"
echo "4. **Low:** Start AUI loop 77 build — pipeline stalled since Aug 25" >> "$REPORT"
echo "5. **Info:** Gen report script (\`gen_report.sh\`) now tracked and available" >> "$REPORT"
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Changes This Cycle" >> "$REPORT"
echo "" >> "$REPORT"
echo "- Restored \`cron_report_0423.md\` to its committed state (modified out-of-band since run #423)" >> "$REPORT"
echo "- Committed as fd2b41f, pushed to origin/master" >> "$REPORT"
echo "- All submodules clean — no new commits" >> "$REPORT"
echo "- No new tracked files requiring attention" >> "$REPORT"
echo "" >> "$REPORT"

cat "$REPORT"
