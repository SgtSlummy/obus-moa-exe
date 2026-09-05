#!/bin/bash
set -e
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "===== NEW FILES SINCE LAST REPORT (0449) ====="
# Report 0449 was at commit de9884a. Check for new files.
git diff --name-status de9884a..HEAD 2>&1
echo ""
echo "===== CURRENT TIME ====="
date -u +"%Y-%m-%d %H:%M:%S UTC"
echo ""
echo "===== BUILD LOOP 76 CONTENT ====="
ls -la build-aui-loop76/OBus/ 2>/dev/null | head -10
echo ""
echo "===== DIST LOOP 76 EXE INFO ====="
ls -la dist-aui-loop76/OBus.exe 2>/dev/null
echo ""
echo "===== ANY NEW BUILD ACTIVITY? ====="
# Check if any build loop dirs were modified in last 24h
find build-aui-loop* -maxdepth 1 -type d -mmin -1440 2>/dev/null | head -5
echo ""
echo "===== RECENT CRON REPORTS (newest 3) ====="
for f in cron_report_0447.md cron_report_0448.md cron_report_0449.md; do
  echo "--- $f ---"
  head -15 "$f" 2>/dev/null
  echo ""
done
echo ""
echo "===== PUSH STATUS SUMMARY (last 10 lines) ====="
tail -10 push_status_new.txt 2>/dev/null
echo ""
echo "===== ANY PENDING CHANGES IN WORKING TREE ====="
git status --short 2>&1
echo ""
echo "===== CRON JOB SELF-CHECK ====="
echo "Job ID: 893c7df0ef71"
echo "Previous run: #449 at 2026-09-05 06:43 UTC"
echo "Current run: #450 at $(date -u +'%Y-%m-%d %H:%M:%S') UTC"
