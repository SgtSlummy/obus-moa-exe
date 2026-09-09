#!/bin/bash
# Push projects and check progress - 2026-09-08 16:46 UTC-7
set -e
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=========================================="
echo "PUSH & PROGRESS REPORT"
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "=========================================="

echo ""
echo "=== GIT STATUS ==="
git status --short

echo ""
echo "=== GIT LOG (last 5 commits) ==="
git log --oneline -5

echo ""
echo "=== REMOTE BRANCH STATUS ==="
git branch -r -v | head -20

echo ""
echo "=== UNPUSHED BRANCHES ==="
for branch in $(git branch --format='%(refname:short)' | grep -v master); do
    local_commit=$(git rev-parse "$branch")
    remote_commit=$(git rev-parse "origin/$branch" 2>/dev/null || echo "NONE")
    if [ "$local_commit" != "$remote_commit" ]; then
        ahead=$(git rev-list --count "$remote_commit..$branch" 2>/dev/null || echo "?")
        echo "  $branch: $ahead commit(s) ahead of origin"
    fi
done

echo ""
echo "=== RECENT REPORTS ==="
ls -la cron_report_*.md 2>/dev/null | tail -5

echo ""
echo "=== LATEST REPORT CONTENT ==="
cat cron_report_latest.md 2>/dev/null || echo "No latest report"

echo ""
echo "=== ACTIVE BUILD DIRECTORIES ==="
ls -la build-aui-loop*/ 2>/dev/null | grep -E "^d" | tail -10

echo ""
echo "=== DIST ARTIFACTS ==="
ls -la dist-aui-loop*/ 2>/dev/null | grep -E "^d" | tail -10

echo ""
echo "=========================================="
echo "END REPORT"
echo "=========================================="
