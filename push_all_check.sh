#!/bin/bash
set -euo pipefail
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=== GIT STATUS ==="
git status -s

echo ""
echo "=== REMOTE BRANCHES ==="
git branch -r

echo ""
echo "=== LOCAL BRANCHES WITH TRACKING ==="
git branch -vv

echo ""
echo "=== PUSHING MASTER ==="
git push origin master 2>&1 || echo "PUSH FAILED for master"

echo ""
echo "=== PUSHING ALL LOCAL BRANCHES WITH REMOTE ==="
for branch in $(git branch --format='%(refname:short)' | grep -v '^\*'); do
    remote=$(git config "branch.$branch.remote" 2>/dev/null || echo "")
    if [ -n "$remote" ]; then
        echo "--- Pushing $branch ---"
        git push "$remote" "$branch" 2>&1 || echo "FAILED: $branch"
    fi
done

echo ""
echo "=== FINAL STATUS ==="
git status -s
echo ""
echo "=== LATEST COMMIT ==="
git log -1 --oneline
