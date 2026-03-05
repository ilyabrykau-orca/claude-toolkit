#!/usr/bin/env bash
# orca-env plugin test runner
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

UNIT_ONLY=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit) UNIT_ONLY=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "========================================"
echo " orca-env plugin test suite"
echo "========================================"
echo "Plugin: $PLUGIN_ROOT"
echo "Date:   $(date)"
echo ""

passed=0; failed=0

run_test_file() {
    local f="$1"
    local name
    name=$(basename "$f")
    echo "--- $name ---"
    chmod +x "$f"
    if bash "$f"; then
        passed=$((passed+1))
        echo "[PASS] $name"
    else
        failed=$((failed+1))
        echo "[FAIL] $name"
    fi
    echo ""
}

echo "=== Unit Tests (no LLM) ==="
for f in "${SCRIPT_DIR}/unit"/test-*.sh; do
    run_test_file "$f"
done

if [ "$UNIT_ONLY" = false ]; then
    if ! command -v claude &>/dev/null; then
        echo "WARNING: claude CLI not found, skipping integration tests"
    else
        echo "=== Integration Tests (LLM) ==="
        for f in "${SCRIPT_DIR}/integration"/test-*.sh; do
            run_test_file "$f"
        done
    fi
fi

echo "========================================"
echo "Passed: $passed  Failed: $failed"
echo "========================================"
[ $failed -eq 0 ] && echo "STATUS: PASSED" && exit 0 || echo "STATUS: FAILED" && exit 1
