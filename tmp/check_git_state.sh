#!/bin/bash
set -euo pipefail

echo "=== Scanning all git repos under /c/Users/Hermes/Documents ==="
find /c/Users/Hermes/Documents -type d -name ".git" -exec dirname {} \; | while read -r repo; do
    echo ""
    echo "### Repository: $repo"
    (
        cd "$repo"
        branch=$(git branch --show-current 2>/dev/null || echo "detached")
        remote=$(git config --get remote.origin.url 2>/dev/null || echo "none")
        ahead=$(git rev-list --count HEAD..origin/HEAD 2>/dev/null || echo "?")
        behind=$(git rev-list --count origin/HEAD..HEAD 2>/dev/null || echo "?")
        porcelain=$(git status --porcelain 2>/dev/null || echo "error")
        
        echo "  Branch: $branch"
        echo "  Remote: $remote"
        echo "  Ahead: $ahead | Behind: $behind"
        echo "  Status:"
        if [ -z "$porcelain" ]; then
            echo "    (clean)"
        else
            echo "$porcelain" | while read -r line; do
                echo "    $line"
            done
        fi
    )
done

echo ""
echo "=== Active background processes (OBus, build, python, ollama, llama, gortex, codex, hermes) ==="
tasklist.exe /fo csv /nh 2>/dev/null | grep -iE "obus|build|python|ollama|llama|gortex|codex|hermes" || echo "(none found)"
