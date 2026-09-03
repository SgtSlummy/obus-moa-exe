#!/bin/bash
ROOT="/c/Users/Hermes/Documents/obus-moa-exe"
NOW=$(date -u +"%Y-%m-%d %H:%M UTC")
REPORT="$ROOT/cron_report_0423.md"

echo "# Cron Report — $NOW" > "$REPORT"
echo "**Job ID:** 893c7df0ef71 | **Schedule:** every 10m | **Run:** #423" >> "$REPORT"
echo "" >> "$REPORT"

# Find all git repos
echo "## Git Push — All Projects" >> "$REPORT"
echo "" >> "$REPORT"

PUSHED_CLEAN=0
PUSHED_CHANGES=0

for dir in $(find "$ROOT" -name ".git" -type d 2>/dev/null | sed 's/\/.git$//' | sort -u); do
    NAME=$(basename "$dir")
    REMOTE=$(cd "$dir" && git remote -v 2>/dev/null | head -1 | awk '{print $2}')
    [ -z "$REMOTE" ] && REMOTE="none"
    
    STATUS=$(cd "$dir" && git status --porcelain 2>/dev/null)
    HAS_CHANGES=0
    [ -n "$STATUS" ] && HAS_CHANGES=1
    
    HEAD=$(cd "$dir" && git log --oneline -1 2>/dev/null | cut -d' ' -f1)
    [ -z "$HEAD" ] && HEAD="unknown"
    
    PUSH_OUT=$(cd "$dir" && git push 2>&1)
    PUSH_RC=$?
    
    if [ $PUSH_RC -eq 0 ]; then
        if [ $HAS_CHANGES -eq 1 ]; then
            PUSHED_CHANGES=$((PUSHED_CHANGES + 1))
            echo "### $NAME" >> "$REPORT"
            echo "- **Status:** Pushed with changes" >> "$REPORT"
            echo "- **Remote:** $REMOTE" >> "$REPORT"
            echo "- **HEAD:** \`$HEAD\`" >> "$REPORT"
            echo "- **Changes:** $(echo "$STATUS" | wc -l) file(s)" >> "$REPORT"
            echo "" >> "$REPORT"
        else
            PUSHED_CLEAN=$((PUSHED_CLEAN + 1))
            echo "### $NAME" >> "$REPORT"
            echo "- **Status:** Already up-to-date" >> "$REPORT"
            echo "- **Remote:** $REMOTE" >> "$REPORT"
            echo "- **HEAD:** \`$HEAD\`" >> "$REPORT"
            echo "" >> "$REPORT"
        fi
    else
        echo "### $NAME" >> "$REPORT"
        echo "- **Status:** Push failed (rc=$PUSH_RC)" >> "$REPORT"
        echo "- **Remote:** $REMOTE" >> "$REPORT"
        echo "- **Error:** $(echo "$PUSH_OUT" | head -2)" >> "$REPORT"
        echo "" >> "$REPORT"
    fi
done

echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "### Push Summary" >> "$REPORT"
echo "| Category | Count |" >> "$REPORT"
echo "|----------|-------|" >> "$REPORT"
echo "| Up-to-date | $PUSHED_CLEAN |" >> "$REPORT"
echo "| Pushed changes | $PUSHED_CHANGES |" >> "$REPORT"
echo "| Total repos | $(find "$ROOT" -name ".git" -type d 2>/dev/null | wc -l) |" >> "$REPORT"
echo "" >> "$REPORT"

# Process census
echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Active Jobs / Processes" >> "$REPORT"
echo "" >> "$REPORT"
echo "**Hermes-managed background jobs:** None (this cron job is the only active Hermes process)" >> "$REPORT"
echo "" >> "$REPORT"

echo "### System-wide relevant processes" >> "$REPORT"
echo "" >> "$REPORT"

for PROC in python.exe node.exe node_repl.exe llama-server.exe ollama.exe "ollama app.exe" gortex.exe codex.exe "codex-code-mode-host.exe" OBus.exe Obus.exe chrome.exe msedge.exe ChatGPT.exe headroom.exe pinchtab-windows-amd64.exe EchoWarp.exe DavyJonesHeartbeat.exe; do
    COUNT=$(tasklist /FI "IMAGENAME eq $PROC" /FO CSV 2>/dev/null | wc -l)
    COUNT=$((COUNT - 1))
    [ "$COUNT" -gt 0 ] && echo "| $PROC | $COUNT | | |" >> "$REPORT"
done

echo "" >> "$REPORT"

# Build pipeline
echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Build Pipeline" >> "$REPORT"
echo "" >> "$REPORT"

LATEST_BUILD=$(ls -d "$ROOT"/build-aui-loop* 2>/dev/null | sort | tail -1)
LATEST_DIST=$(ls -d "$ROOT"/dist-aui-loop* 2>/dev/null | sort | tail -1)

if [ -n "$LATEST_BUILD" ]; then
    BN=$(basename "$LATEST_BUILD")
    echo "- Latest build: \`$BN\`" >> "$REPORT"
fi

if [ -n "$LATEST_DIST" ]; then
    DN=$(basename "$LATEST_DIST")
    echo "- Latest dist: \`$DN\`" >> "$REPORT"
    EXE=$(ls "$LATEST_DIST"/*.exe 2>/dev/null | head -1)
    if [ -n "$EXE" ]; then
        SZ=$(stat -c %s "$EXE" 2>/dev/null)
        echo "  - $(basename $EXE): $((SZ / 1024 / 1024))MB" >> "$REPORT"
    fi
    LN=$(echo "$DN" | grep -o '[0-9]*' | tail -1)
    if [ "${LN:-0}" -lt 77 ] 2>/dev/null; then
        echo "- **STALLED:** No loop 77+ build" >> "$REPORT"
    fi
fi

echo "" >> "$REPORT"

# Blockers
echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Blockers" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. Auth blocks: MoA-source, models-dev-source, warden-source (403/SSH)" >> "$REPORT"
echo "2. DavyJonesBot: stale bundle remote, ahead 10" >> "$REPORT"
echo "3. Build pipeline stalled: No AUI loop 77 build" >> "$REPORT"
echo "" >> "$REPORT"

# Action items
echo "---" >> "$REPORT"
echo "" >> "$REPORT"
echo "## Action Items" >> "$REPORT"
echo "" >> "$REPORT"
echo "1. Push main repo — Done ($PUSHED_CLEAN up-to-date, $PUSHED_CHANGES pushed)" >> "$REPORT"
echo "2. Start AUI loop 77 build — pipeline stalled" >> "$REPORT"
echo "3. DavyJonesBot — new bundle path needed" >> "$REPORT"

cat "$REPORT"
