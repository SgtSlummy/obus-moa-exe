#!/bin/bash
set -e

echo "=== Pushing all branches to origin ==="
cd /c/Users/Hermes/Documents/obus-moa-exe

# Push all branches
git push origin --all 2>&1 | tee push_branches.txt

echo ""
echo "=== Pushing all tags ==="
git push origin --tags 2>&1 | tee -a push_branches.txt

echo ""
echo "=== Git status ==="
git status --short 2>&1 | tee git_status.txt

echo ""
echo "=== Recent commits ==="
git log --oneline -10 2>&1 | tee git_log.txt

echo ""
echo "=== Unpushed commits ==="
git log --oneline @{u}..HEAD 2>&1 | tee git_unpushed.txt || echo "No upstream or up to date"

echo ""
echo "=== Build status ==="
cat build_status_report.txt 2>/dev/null || echo "No build status report"

echo ""
echo "=== Check for active build loops ==="
for dir in build-aui-loop*/; do
    if [ -f "$dir/build_status.txt" ]; then
        echo "--- $dir ---"
        cat "$dir/build_status.txt" 2>/dev/null || echo "No status file"
        echo ""
    fi
done

echo ""
echo "=== Check deploy directory ==="
ls -la deploy/ 2>/dev/null || echo "No deploy directory"

echo ""
echo "=== Check dist directory for recent EXEs ==="
ls -lt dist/*.exe 2>/dev/null | head -5 || echo "No EXE files in dist/"

echo ""
echo "=== Check latest dist subdirectory ==="
ls -lt dist-*/ 2>/dev/null | head -10 || echo "No dist-* directories"

echo ""
echo "=== Package directories status ==="
for dir in package-dist312-consolidated-v*/; do
    if [ -f "$dir/package_status.txt" ]; then
        echo "--- $dir ---"
        cat "$dir/package_status.txt" 2>/dev/null || echo "No status file"
        echo ""
    fi
done

echo ""
echo "=== Cron reports (last 5) ==="
ls -lt cron_report_*.md 2>/dev/null | head -5

echo ""
echo "=== Process check for running builds ==="
ps aux | grep -E "(python|node|electron|obus)" | grep -v grep || echo "No relevant processes running"

echo ""
echo "=== Done ==="
