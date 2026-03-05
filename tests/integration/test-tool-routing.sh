#!/usr/bin/env bash
# Integration test: verify Claude uses Codanna for code search (not native Read/Grep)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${SCRIPT_DIR}/../helpers.sh"

passed=0; failed=0

echo "=== Integration: tool routing ==="
echo ""

if ! command -v claude &>/dev/null; then
    echo "[SKIP] claude CLI not found"
    exit 0
fi

# Claude should use mcp__codanna__ tools for finding Python code
echo "Test 1: Codanna used for Python code search"
output=$(run_claude \
    "$(cat "${SCRIPT_DIR}/prompts/python-code-search.txt")" \
    120 \
    "$PLUGIN_ROOT" \
    "/Users/ilyabrykau/src/orca")

if assert_contains "$output" "mcp__codanna__" "Codanna tool called"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi
if assert_not_contains "$output" '"name":"Read"' "native Read NOT used for code"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi
if assert_not_contains "$output" '"name":"Grep"' "native Grep NOT used for code"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi

echo ""
echo "Passed: $passed  Failed: $failed"
[ $failed -eq 0 ] && exit 0 || exit 1
