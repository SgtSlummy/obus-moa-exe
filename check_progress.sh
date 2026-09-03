#!/bin/bash
cd /c/Users/Hermes/Documents/obus-moa-exe

echo "=== Git Status (obus-moa-exe) ==="
git status --short

echo ""
echo "=== Recent Commits ==="
git log --oneline -3

echo ""
echo "=== Latest Dist Directories ==="
ls -la dist-aui-loop76/ 2>/dev/null
ls dist-aui-loop77/ 2>/dev/null && echo "LOOP 77 EXISTS" || echo "NO LOOP 77"

echo ""
echo "=== Build Directories ==="
ls build-aui-loop76/ 2>/dev/null
ls build-aui-loop77/ 2>/dev/null && echo "BUILD LOOP 77 EXISTS" || echo "NO BUILD LOOP 77"

echo ""
echo "=== .hermes/package-* ==="
ls -la .hermes/package-* 2>/dev/null

echo ""
echo "=== Latest cron report ==="
cat cron_report_latest.md 2>/dev/null | head -30

echo ""
echo "=== Push status ==="
cat push_status.txt | head -20

echo ""
echo "=== Active processes (OBus, build, python) ==="
tasklist.exe 2>/dev/null | grep -iE "OBus|build|python|ollama|llama|gortex|codex|hermes" | head -30
