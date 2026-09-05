#!/bin/bash
cd /c/Users/Hermes/Documents/obus-moa-exe || exit 1

echo "=== Git Status ==="
git status --short 2>&1

echo ""
echo "=== Git Remote ==="
git remote -v 2>&1

echo ""
echo "=== Last 5 Commits ==="
git log --oneline -5 2>&1

echo ""
echo "=== Unpushed Commits ==="
git log --oneline @{u}..HEAD 2>&1 || echo "(no upstream or up-to-date)"

echo ""
echo "=== Branches ==="
git branch -vv 2>&1 | head -20

echo ""
echo "=== Recent Cron Reports ==="
ls -la cron_report_*.md 2>&1 | tail -10
