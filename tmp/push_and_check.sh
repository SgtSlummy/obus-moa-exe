#!/bin/bash
# Push changed repos and list active background jobs

echo "=== Pushing Git Repositories ==="

# obus-moa-exe
cd /c/Users/Hermes/Documents/obus-moa-exe
echo "--- obus-moa-exe ---"
git status --short
git push origin master 2>&1 || echo "PUSH FAILED"

# ComfyUI
cd /c/Users/Hermes/Documents/comfy/ComfyUI
echo "--- ComfyUI ---"
git status --short
git pull origin master 2>&1 || true
git push origin master 2>&1 || echo "PUSH FAILED (may not have write access)"

# Tarot-Router
cd /c/Users/Hermes/Documents/Tarot-Router
echo "--- Tarot-Router ---"
git status --short
git push origin main 2>&1 || echo "PUSH FAILED"

echo ""
echo "=== Active processes (OBus, build, python, ollama, llama, gortex, codex, hermes) ==="
tasklist.exe /fo csv /nh 2>/dev/null | grep -iE "obus|build|python|ollama|llama|gortex|codex|hermes|warp" || echo "(none found)"
