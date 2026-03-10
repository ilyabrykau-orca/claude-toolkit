#!/usr/bin/env bash
# Unit test: pre-read-use hook — line limit enforcement
# Exit codes: 0=allow, 1=warn (large), 2=block (huge)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/../helpers.sh"

HOOK="${PLUGIN_ROOT}/hooks/pre-read-use"

# Skip gracefully if hook not yet created by the other agent
if [ ! -f "$HOOK" ]; then
    echo "=== Unit: pre-read-use — SKIPPED (hook not yet created) ==="
    exit 0
fi

passed=0; failed=0

echo "=== Unit: pre-read-use enforcement ==="
echo ""

# Helper: run hook, capture exit code
run_hook() {
    local json="$1"
    local rc=0
    echo "$json" | bash "$HOOK" >/dev/null 2>&1 || rc=$?
    echo "$rc"
}

test_exit() {
    local json="$1"
    local test_name="$2"
    local expected="$3"
    local actual
    actual=$(run_hook "$json")
    if [ "$actual" = "$expected" ]; then
        echo "  [PASS] $test_name (exit $actual)"
        passed=$((passed+1))
    else
        echo "  [FAIL] $test_name (expected exit $expected, got $actual)"
        failed=$((failed+1))
    fi
}

# ── Allow: small limits (exit 0) ────────────────────────────────────────────

echo "--- Allow: small limits ---"

test_exit '{"tool_name":"Read","tool_input":{"file_path":"config.yaml","limit":100}}' \
    "limit=100 allowed" 0

test_exit '{"tool_name":"Read","tool_input":{"file_path":"small.py","limit":400}}' \
    "limit=400 (boundary) allowed" 0

# ── Warn: medium limits (exit 1) ────────────────────────────────────────────

echo ""
echo "--- Warn: medium limits ---"

test_exit '{"tool_name":"Read","tool_input":{"file_path":"medium.py","limit":401}}' \
    "limit=401 warns" 1

test_exit '{"tool_name":"Read","tool_input":{"file_path":"medium.py","limit":600}}' \
    "limit=600 warns" 1

# ── Block: huge limits (exit 2) ──────────────────────────────────────────────

echo ""
echo "--- Block: huge limits ---"

test_exit '{"tool_name":"Read","tool_input":{"file_path":"huge.py","limit":601}}' \
    "limit=601 blocked" 2

test_exit '{"tool_name":"Read","tool_input":{"file_path":"huge.py","limit":2000}}' \
    "limit=2000 blocked" 2

# ── Allow: non-Read tool ─────────────────────────────────────────────────────

echo ""
echo "--- Non-Read tool ---"

test_exit '{"tool_name":"Edit","tool_input":{"file_path":"foo.py"}}' \
    "Edit tool passes through" 0

# ── File-size heuristic: no limit on small file ─────────────────────────────

echo ""
echo "--- No-limit file heuristics ---"

TMPFILE_SMALL=$(mktemp)
# Write 50 lines to a small temp file
for i in $(seq 1 50); do echo "line $i"; done > "$TMPFILE_SMALL"

test_exit "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$TMPFILE_SMALL\"}}" \
    "no limit, small file (50 lines) allowed" 0

rm -f "$TMPFILE_SMALL"

# ── File-size heuristic: no limit on large file ─────────────────────────────

TMPFILE_LARGE=$(mktemp)
# Write 800 lines to a large temp file
for i in $(seq 1 800); do echo "line $i of the large file with some content"; done > "$TMPFILE_LARGE"

test_exit "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"$TMPFILE_LARGE\"}}" \
    "no limit, large file (800 lines) blocked" 2

rm -f "$TMPFILE_LARGE"

# ── Allow: non-existent file (fail open) ─────────────────────────────────────

echo ""
echo "--- Edge cases ---"

test_exit '{"tool_name":"Read","tool_input":{"file_path":"/nonexistent/path/to/file.py"}}' \
    "non-existent file (fail open)" 0

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "Passed: $passed  Failed: $failed"
[ $failed -eq 0 ] && exit 0 || exit 1
