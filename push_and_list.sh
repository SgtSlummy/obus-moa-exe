#!/usr/bin/env bash
set -euo pipefail
echo "=== Git Push Report ==="

git_dirs=$(find . -type d -name ".git" -printf '%h\n')
if [ -z "$git_dirs" ]; then
  echo "No git repositories found."
else
  echo "$git_dirs" | while read -r dir; do
    echo
    echo "Repository: $dir"
    echo "Status (porcelain):"
    git -C "$dir" status --porcelain | cat -n || echo "error status"
    remote=$(git -C "$dir" config --get remote.origin.url 2>/dev/null || echo "none")
    echo "Remote URL: $remote"
    if [ "$remote" != "none" ]; then
      echo "Pushing to remote..."
      git -C "$dir" push -v || echo "push failed"
    else
      echo "No remote configured, skipping."
    fi
  done
fi

echo
echo "=== Active background jobs ==="
if command -v tasklist > /dev/null 2>&1; then
  tasklist /fo csv /nh
else
  echo "tasklist command not available."
fi