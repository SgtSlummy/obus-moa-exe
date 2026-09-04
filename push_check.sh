#!/bin/bash
set -e
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=== PUSHING MAIN REPO ==="
git push origin codex/autonomy-context-agents 2>&1 || echo "PUSH FAILED: $?"

echo ""
echo "=== GIT STATUS ==="
git status --short

echo ""
echo "=== MOST RECENT COMMIT ==="
git log --oneline -1

echo ""
echo "=== REMOTE BRANCHES ==="
git ls-remote --heads origin 2>&1 | tail -5
