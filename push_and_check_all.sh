#!/bin/bash
# Push all local branches and check for active jobs

set -e

cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=== Checking git status ==="
git status --short

echo ""
echo "=== Branches with unpushed commits ==="
git branch -vv | grep -v "origin/.*\[gone\]" | while read branch; do
    branchname=$(echo "$branch" | awk '{print $1}')
    if echo "$branch" | grep -q "\[ahead"; then
        echo "  $branch"
    fi
done

echo ""
echo "=== Pushing all branches ==="
git push --all origin 2>&1 || echo "Push had issues"

echo ""
echo "=== Push output ==="
cat push_output.txt 2>/dev/null || echo "No push_output.txt"

echo ""
echo "=== Active background processes ==="
ps aux | grep -E "(python|node|java|build|test)" | grep -v grep | head -20

echo ""
echo "=== Recent cron reports ==="
ls -lt cron_report_*.md 2>/dev/null | head -10

echo ""
echo "=== Latest cron report ==="
cat cron_report_latest.md 2>/dev/null || echo "No latest report"

echo ""
echo "=== Check progress ==="
bash check_progress.sh 2>/dev/null || echo "check_progress.sh not available or failed"

echo ""
echo "=== Build status ==="
cat build_status_report.txt 2>/dev/null || echo "No build status"

echo ""
echo "=== Done ==="
