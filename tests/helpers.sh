#!/usr/bin/env bash
# Test helpers for orca-env plugin tests

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

assert_contains() {
    local output="$1"
    local pattern="$2"
    local test_name="${3:-test}"
    if echo "$output" | grep -qE "$pattern"; then
        echo "  [PASS] $test_name"
        return 0
    else
        echo "  [FAIL] $test_name"
        echo "  Expected pattern: $pattern"
        echo "  In output:"
        echo "$output" | sed 's/^/    /'
        return 1
    fi
}

assert_not_contains() {
    local output="$1"
    local pattern="$2"
    local test_name="${3:-test}"
    if echo "$output" | grep -qE "$pattern"; then
        echo "  [FAIL] $test_name"
        echo "  Did not expect: $pattern"
        return 1
    else
        echo "  [PASS] $test_name"
        return 0
    fi
}

assert_valid_json() {
    local output="$1"
    local test_name="${2:-valid JSON}"
    if echo "$output" | jq . >/dev/null 2>&1; then
        echo "  [PASS] $test_name"
        return 0
    else
        echo "  [FAIL] $test_name - not valid JSON"
        echo "$output" | sed 's/^/    /'
        return 1
    fi
}

assert_json_field() {
    local output="$1"
    local field="$2"
    local test_name="${3:-JSON field $field}"
    local value
    value=$(echo "$output" | jq -r "$field" 2>/dev/null)
    if [ -n "$value" ] && [ "$value" != "null" ]; then
        echo "  [PASS] $test_name"
        return 0
    else
        echo "  [FAIL] $test_name - field '$field' missing or null"
        return 1
    fi
}

run_claude() {
    local prompt="$1"
    local timeout="${2:-120}"
    local plugin_dir="${3:-$PLUGIN_ROOT}"
    local work_dir="${4:-$PLUGIN_ROOT}"
    local output_file
    output_file=$(mktemp)
    (
        cd "$work_dir"
        timeout "$timeout" claude -p "$prompt" \
            --plugin-dir "$plugin_dir" \
            --dangerously-skip-permissions \
            --max-turns 3 \
            --output-format stream-json 2>&1
    ) > "$output_file" || true
    cat "$output_file"
    rm -f "$output_file"
}

export -f assert_contains
export -f assert_not_contains
export -f assert_valid_json
export -f assert_json_field
export -f run_claude
export PLUGIN_ROOT
