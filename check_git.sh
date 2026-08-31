#!/bin/bash
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=== GIT STATUS ==="
git status 2>&1 | head -30

echo ""
echo "=== CURRENT BRANCH ==="
git branch --show-current 2>&1

echo ""
echo "=== REMOTES ==="
git remote -v 2>&1

echo ""
echo "=== RECENT COMMITS ==="
git log --oneline -5 2>&1

echo ""
echo "=== untracked files (first 20) ==="
git status --short 2>&1 | head -20
