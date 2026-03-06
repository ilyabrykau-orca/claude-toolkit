#!/usr/bin/env bash
# Unit test: escape_for_json edge cases
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/../helpers.sh"

# Extract escape_for_json from the hook
eval "$(sed -n '/^escape_for_json/,/^}/p' "${PLUGIN_ROOT}/hooks/session-start")"

passed=0; failed=0

echo "=== Unit: JSON escaping edge cases ==="
echo ""

# Test: double quotes
result=$(escape_for_json 'say "hello"')
if assert_contains "$result" 'say \\"hello\\"' "double quotes escaped"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi

# Test: backslashes
result=$(escape_for_json 'path\to')
if assert_contains "$result" 'path\\\\to' "backslashes escaped"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi

# Test: newlines
result=$(escape_for_json $'line1\nline2')
if assert_contains "$result" 'line1\\nline2' "newlines escaped"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi

# Test: tabs
result=$(escape_for_json $'col1\tcol2')
if assert_contains "$result" 'col1\\tcol2' "tabs escaped"; then
    passed=$((passed+1)); else failed=$((failed+1))
fi

# Test: full SKILL.md wrapped in JSON validates with jq
skill_content=$(cat "${PLUGIN_ROOT}/skills/orca-setup/SKILL.md")
escaped_skill=$(escape_for_json "$skill_content")
json_wrapper="{\"content\": \"${escaped_skill}\"}"
if echo "$json_wrapper" | jq . >/dev/null 2>&1; then
    echo "  [PASS] SKILL.md content in JSON validates with jq"
    passed=$((passed+1))
else
    echo "  [FAIL] SKILL.md content in JSON validates with jq"
    echo "  jq error on wrapped SKILL.md"
    failed=$((failed+1))
fi

# Test: markdown table with pipes and backticks
md_table='| Tool | Use `this` | Result |
| --- | --- | --- |
| `grep` | pattern\here | "found" |'
escaped_table=$(escape_for_json "$md_table")
json_table="{\"table\": \"${escaped_table}\"}"
if echo "$json_table" | jq . >/dev/null 2>&1; then
    echo "  [PASS] markdown table with pipes and backticks survives escaping"
    passed=$((passed+1))
else
    echo "  [FAIL] markdown table with pipes and backticks survives escaping"
    echo "  jq error on markdown table"
    failed=$((failed+1))
fi

echo ""
echo "Passed: $passed  Failed: $failed"
[ $failed -eq 0 ] && exit 0 || exit 1
