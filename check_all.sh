set -e
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "===== GIT STATUS (main) ====="
git status --short 2>&1 | head -60
echo ""
echo "===== GIT LOG (last 5) ====="
git log --oneline -5 2>&1
echo ""
echo "===== GIT BRANCHES ====="
git branch -vv 2>&1 | head -20
echo ""
echo "===== GIT REMOTES ====="
git remote -v 2>&1
echo ""
echo "===== GIT PUSH STATUS (full) ====="
git push --dry-run 2>&1 | head -40
echo ""
echo "===== LATEST PUSH STATUS FILE ====="
cat push_status_new.txt 2>/dev/null | tail -40
echo ""
echo "===== ACTIVE BUILD DIRECTORY (newest, non-empty) ====="
ls -lt build-aui-loop* 2>/dev/null | head -5
echo ""
echo "===== LATEST DIST DIRECTORY ====="
ls -lt dist-aui-loop* 2>/dev/null | head -5
echo ""
echo "===== PYTHON VENV CHECK ====="
ls -la .venv/bin/python 2>/dev/null && .venv/bin/python --version 2>/dev/null || echo "no .venv python"
echo ""
echo "===== CRON REPORT LATEST ====="
cat cron_report_latest.md 2>/dev/null | head -30
echo ""
echo "===== ACTIVE JOBS FROM LATEST REPORT ====="
grep -i "active\|running\|in progress\|pending\|queue" cron_report_latest.md 2>/dev/null | head -20
