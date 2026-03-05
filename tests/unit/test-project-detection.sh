#!/usr/bin/env bash
# Unit test: session-start hook project detection
# Tests hook output from different $PWD values. No LLM needed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/../helpers.sh"

HOOK="${PLUGIN_ROOT}/hooks/session-start"
passed=0; failed=0

run_test() {
    local dir="$1"
    local expected_project="$2"
    local test_name="$3"
    local output
    output=$(cd "$dir" 2>/dev/null && bash "$HOOK" 2>/dev/null || echo '{"error":"hook_failed"}')
    if [ -n "$expected_project" ]; then
        if assert_contains "$output" "activate_project.*$expected_project|$expected_project.*activate_project" "$test_name"; then
            passed=$((passed+1))
        else
            failed=$((failed+1))
        fi
    else
        if assert_not_contains "$output" "activate_project" "$test_name (no activation expected)"; then
            passed=$((passed+1))
        else
            failed=$((failed+1))
        fi
    fi
}

echo "=== Unit: project detection ==="
echo ""

run_test "/Users/ilyabrykau/src"                         "orca-unified"          "src/ → orca-unified"
run_test "/Users/ilyabrykau/src/orca"                    "orca"                  "orca/ → orca"
run_test "/Users/ilyabrykau/src/orca/base_api"           "orca"                  "orca subdir → orca"
run_test "/Users/ilyabrykau/src/orca-sensor"             "orca-sensor"           "orca-sensor/ → orca-sensor"
run_test "/Users/ilyabrykau/src/orca-sensor/pkg/agent"   "orca-sensor"           "orca-sensor subdir → orca-sensor"
run_test "/Users/ilyabrykau/src/orca-runtime-sensor"     "orca-runtime-sensor"   "runtime-sensor/ → orca-runtime-sensor"
run_test "/Users/ilyabrykau/src/helm-charts"             "helm-charts"           "helm-charts/ → helm-charts"
run_test "/tmp"                                           ""                      "/tmp → no activation"
run_test "/Users/ilyabrykau"                             ""                      "home → no activation"

echo ""
echo "Passed: $passed  Failed: $failed"
[ $failed -eq 0 ] && exit 0 || exit 1
