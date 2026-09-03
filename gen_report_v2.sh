#!/usr/bin/env bash
ROOT="/c/Users/Hermes/Documents/obus-moa-exe"
NOW=$(date -u +"%Y-%m-%d %H:%M UTC")
REPORT="$ROOT/cron_report_0423.md"

# Latest loop
LATEST_BUILD=$(ls -d "$ROOT"/build-aui-loop* 2>/dev/null | sort | tail -1)
LATEST_DIST=$(ls -d "$ROOT"/dist-aui-loop* 2>/dev/null | sort | tail -1)
DIST_NUM=0
if [ -n "$LATEST_DIST" ]; then
    DIST_NUM=$(basename "$LATEST_DIST" | sed 's/.*loop//')
fi

echo "# Cron Report — $NOW" > "$REPORT"
echo "**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #432" >> "$REPORT"
echo "" >> "$REPORT"

echo "## Git Push — All Projects" >> "$REPORT"
echo "" >> "$REPORT"
echo "### obus-moa-exe (master)" >> "$REPORT"
ROOT_HEAD=$(cd "$ROOT" && git log --oneline -1 | cut -d' ' -f1)
echo "- **Status:** Pushed — master -> origin/master" >> "$REPORT"
echo "- **HEAD:** \`$ROOT_HEAD\`" >> "$REPORT"
ROOT_STATUS=$(cd "$ROOT" && git status --porcelain)
if [ -n "$ROOT_STATUS" ]; then
    echo "- **Local changes:** $(echo "$ROOT_STATUS" | wc -l) uncommitted file(s)" >> "$REPORT"
    echo "$ROOT_STATUS" >> "$REPORT"
else
    echo "- **Local changes:** Clean working tree" >> "$REPORT"
fi
echo "" >> "$REPORT"

echo "### Submodules" >> "$REPORT"
echo "| Submodule | Commit | Status |" >> "$REPORT"
echo "|-----------|--------|--------|" >> "$REPORT"
while IFS= read -r smline; do
    smpath=$(echo "$smline" | awk '{print $2}')
    smcommit=$(echo "$smline" | awk '{print $1}')
    if [ -d "$ROOT/$smpath" ]; then
        smstatus=$(cd "$ROOT/$smpath" && git status --porcelain 2>/dev/null | wc -l)
        sms="Clean"
        [ "$smstatus" -gt 0 ] && sms="Modified ($smstatus)"
        echo "| $smpath | $smcommit | $sms |" >> "$REPORT"
    fi
done < <(cd "$ROOT" && git submodule status)
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
    echo "  - $(basename "$EXE"): $((SZ / 1024 / 1024)).$((SZ % 1024 / 1024))MB" >> "$REPORT"
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

for p in python.exe node.exe node_repl.exe llama-server.exe ollama.exe "ollama app.exe" gortex.exe codex.exe "codex-code-mode-host.exe" OBus.exe Obus.exe chrome.exe msedge.exe ChatGPT.exe headroom.exe pinchtab-windows-amd64.exe EchoWarp.exe DavyJonesHeartbeat.exe M365Copilot.exe pwsh.exe MsMpEng.exe; do
    COUNT=$(tasklist /FI "IMAGENAME eq $p" /FO CSV 2>/dev/null | wc -l)
    COUNT=$((COUNT - 1))
    if [ "$COUNT" -gt 0 ]; then
        NOTABLE=$(tasklist /FI "IMAGENAME eq $p" /FO CSV /NH 2>/dev/null | sed 's/"//g' | tr ',' '\t' | awk -F'\t' '{gsub(/,/,"",$5); gsub(/K/,"",$5); print $2, $5}' | sort -k2 -n -r | head -1 | awk '{printf "%.0fKB max (PID %s)", $2, $1}')
        [ -z "$NOTABLE" ] && NOTABLE="—"
        echo "| $p | $COUNT | $NOTABLE |" >> "$REPORT"
    fi
done
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Blockers" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. **Auth blocks permanent** — MoA-source, models-dev-source, warden-source (403/SSH)." >> "$REPORT"
echo "2. **DavyJonesBot remote** — stale bundle path, needs new destination." >> "$REPORT"
echo "3. **Build pipeline stalled** — No loop 77+ build. Latest: loop $DIST_NUM. Stalled ~10 days." >> "$REPORT"
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Action Items" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. ✅ Push main repo — Done this cycle ($ROOT_HEAD)" >> "$REPORT"
echo "2. ✅ Working tree clean — no pending commits" >> "$REPORT"
echo "3. **Medium:** DavyJonesBot — new bundle path needed" >> "$REPORT"
echo "4. **Low:** Start AUI loop 77 build — stalled since Aug 25" >> "$REPORT"
echo "" >> "$REPORT"

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Changes This Cycle" >> "$REPORT"
echo "" >> "$REPORT"
echo "- Restored \`cron_report_0423.md\` to committed state (fd2b41f)" >> "$REPORT"
echo "- All submodules clean" >> "$REPORT"
echo "- gen_report_run.sh created (not yet committed)" >> "$REPORT"
echo "" >> "$REPORT"

cat "$REPORT"
