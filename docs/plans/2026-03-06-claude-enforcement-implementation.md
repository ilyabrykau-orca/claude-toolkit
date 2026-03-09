# Claude Enforcement Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic Claude hook enforcement to `orca-env-plugin` so config changes are validated, risky tool usage is blocked by explicit policy, verification evidence is recorded, and tasks cannot complete without required successful checks.

**Architecture:** Keep shell as the hook runtime. Move reusable behavior into `lib/` helpers, keep event scripts in `hooks/`, and store explicit deterministic policy in `policies/`. Use a narrow `PostToolUse` recorder to capture touched files and successful verification commands for later `TaskCompleted` enforcement.

**Tech Stack:** Bash, jq, Claude Code command hooks, the existing shell test runner, and targeted Claude CLI integration tests.

---

### Task 1: Add the shared hook framework

**Files:**
- Create: `lib/json.sh`
- Create: `lib/hook-output.sh`
- Create: `lib/session-state.sh`
- Test: `tests/unit/test-hook-lib.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-hook-lib.sh` with focused checks for:
- JSON input reading
- JSON field extraction
- `emit_allow`
- `emit_block`
- per-session state path generation

Minimal test shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

source "${PLUGIN_ROOT}/lib/json.sh"
source "${PLUGIN_ROOT}/lib/hook-output.sh"
source "${PLUGIN_ROOT}/lib/session-state.sh"

input='{"session_id":"s1","hook_event_name":"PreToolUse"}'
value=$(printf '%s' "$input" | json_get '.session_id')
[ "$value" = "s1" ]

allow=$(emit_allow "PreToolUse")
printf '%s' "$allow" | jq -e '.hookSpecificOutput.hookEventName == "PreToolUse"' >/dev/null
```

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-hook-lib.sh --verbose
```

Expected: FAIL because the new `lib/*.sh` files do not exist yet.

**Step 3: Write minimal implementation**

Create the helper files with minimal functions:

`lib/json.sh`

```bash
json_get() {
    local query="$1"
    jq -r "$query"
}
```

`lib/hook-output.sh`

```bash
emit_allow() {
    local event_name="$1"
    jq -n --arg event "$event_name" '{hookSpecificOutput:{hookEventName:$event}}'
}

emit_block() {
    local event_name="$1"
    local reason="$2"
    jq -n --arg event "$event_name" --arg reason "$reason" \
        '{hookSpecificOutput:{hookEventName:$event}, decision:"block", reason:$reason}'
}
```

`lib/session-state.sh`

```bash
state_dir_for_session() {
    local session_id="$1"
    printf '%s/%s\n' "${TMPDIR:-/tmp}/orca-env-plugin-state" "$session_id"
}
```

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-hook-lib.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add lib/json.sh lib/hook-output.sh lib/session-state.sh tests/unit/test-hook-lib.sh
git commit -m "test: add shared hook framework coverage"
```

---

### Task 2: Add config validation before Claude config changes apply

**Files:**
- Create: `lib/config-validate.sh`
- Create: `hooks/config-change`
- Modify: `hooks/hooks.json`
- Test: `tests/unit/test-config-change.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-config-change.sh` to cover:
- valid JSON config allows
- malformed JSON blocks
- missing referenced script blocks
- unknown hook event blocks

Minimal blocking expectation:

```bash
printf '%s' '{"hook_event_name":"ConfigChange","source":"project_settings","file_path":"/tmp/bad.json"}' \
    | bash hooks/config-change
```

Expected behavior: exits `0` with JSON block decision when the target config is invalid.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-config-change.sh --verbose
```

Expected: FAIL because `hooks/config-change` and `lib/config-validate.sh` do not exist.

**Step 3: Write minimal implementation**

`lib/config-validate.sh` should:
- parse the target file with `jq`
- verify `.hooks` exists when the file contains hook config
- verify every `type:"command"` entry has a non-empty `command`

`hooks/config-change` should:
- read hook input JSON from stdin
- inspect `file_path`
- call `lib/config-validate.sh`
- emit allow or block JSON through `lib/hook-output.sh`

Update `hooks/hooks.json` to register:

```json
"ConfigChange": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" config-change",
        "timeout": 10
      }
    ]
  }
]
```

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-config-change.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add lib/config-validate.sh hooks/config-change hooks/hooks.json tests/unit/test-config-change.sh
git commit -m "feat: validate hook config changes before activation"
```

---

### Task 3: Add deterministic `PreToolUse` policy

**Files:**
- Create: `policies/protected-paths.txt`
- Create: `policies/bash-denylist.txt`
- Create: `hooks/pre-tool-use`
- Test: `tests/unit/test-pre-tool-use.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-pre-tool-use.sh` to cover:
- block `Edit` or `Write` on protected config files
- block `Bash` with an explicit denylisted destructive command
- allow non-protected edits
- allow safe bash commands

Minimal expectations:

```bash
printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Edit","tool_input":{"file_path":"hooks/hooks.json"}}' \
    | bash hooks/pre-tool-use
```

Expected: JSON block decision.

```bash
printf '%s' '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"rm -rf hooks"}}' \
    | bash hooks/pre-tool-use
```

Expected: exit `2` with a blocking reason on stderr.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-pre-tool-use.sh --verbose
```

Expected: FAIL because the policy files and hook do not exist.

**Step 3: Write minimal implementation**

Create `policies/protected-paths.txt`:

```text
hooks/hooks.json
.claude/settings.json
.claude/settings.local.json
```

Create `policies/bash-denylist.txt`:

```text
rm -rf
git reset --hard
git checkout --
```

Create `hooks/pre-tool-use` so it:
- reads stdin JSON
- blocks `Edit|Write` when `tool_input.file_path` matches a protected path
- blocks `Bash` when `tool_input.command` matches a denylisted pattern
- emits allow JSON for everything else

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-pre-tool-use.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add policies/protected-paths.txt policies/bash-denylist.txt hooks/pre-tool-use tests/unit/test-pre-tool-use.sh
git commit -m "feat: add deterministic pre-tool enforcement policy"
```

---

### Task 4: Record edited files and successful verification commands

**Files:**
- Create: `policies/verification-rules.sh`
- Create: `hooks/post-tool-use`
- Modify: `hooks/hooks.json`
- Modify: `lib/session-state.sh`
- Test: `tests/unit/test-post-tool-use.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-post-tool-use.sh` to verify:
- `Edit` stores touched file paths for the session
- `Write` stores touched file paths for the session
- successful `Bash` verification commands are recorded
- unrelated bash commands are ignored

Verification rule example in `policies/verification-rules.sh`:

```bash
verification_command_for_path() {
    case "$1" in
        hooks/*|skills/*|commands/*|tests/*) echo "bash tests/run-all.sh --unit" ;;
        *) echo "" ;;
    esac
}
```

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-post-tool-use.sh --verbose
```

Expected: FAIL because the recorder hook does not exist.

**Step 3: Write minimal implementation**

Extend `lib/session-state.sh` with helpers to:
- create a state directory for the session
- append touched file paths into `touched-files.txt`
- write successful verification commands into `verification.log`

Create `hooks/post-tool-use` so it:
- records `tool_input.file_path` for `Edit` and `Write`
- records successful `Bash` commands only when they match a known verification rule
- emits allow JSON and never blocks

Update `hooks/hooks.json` to register:

```json
"PostToolUse": [
  {
    "matcher": "Edit|Write|Bash",
    "hooks": [
      {
        "type": "command",
        "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" post-tool-use",
        "timeout": 10
      }
    ]
  }
]
```

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-post-tool-use.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add policies/verification-rules.sh hooks/post-tool-use hooks/hooks.json lib/session-state.sh tests/unit/test-post-tool-use.sh
git commit -m "feat: record verification evidence for task enforcement"
```

---

### Task 5: Block `TaskCompleted` until verification has passed

**Files:**
- Create: `hooks/task-completed`
- Test: `tests/unit/test-task-completed.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-task-completed.sh` to cover:
- task completion blocks when touched files require verification and none has passed
- task completion allows when required verification was recorded successfully
- task completion allows when no touched file maps to a required verification command

Minimal expected block case:

```bash
printf '%s' '{"hook_event_name":"TaskCompleted","session_id":"s1","task_subject":"update hook"}' \
    | bash hooks/task-completed
```

Expected: block decision if `touched-files.txt` contains `hooks/pre-tool-use` and `verification.log` has no matching successful command.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-task-completed.sh --verbose
```

Expected: FAIL because `hooks/task-completed` does not exist.

**Step 3: Write minimal implementation**

Create `hooks/task-completed` so it:
- loads the session state
- calculates required verification commands for touched files using `policies/verification-rules.sh`
- blocks if any required command has not been recorded as successful
- returns a clear reason naming the required command

Minimal behavior:

```bash
missing="bash tests/run-all.sh --unit"
emit_block "TaskCompleted" "Required verification has not passed: ${missing}"
```

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-task-completed.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add hooks/task-completed tests/unit/test-task-completed.sh
git commit -m "feat: require verification before task completion"
```

---

### Task 6: Add `InstructionsLoaded` consistency checks

**Files:**
- Create: `hooks/instructions-loaded`
- Test: `tests/unit/test-instructions-loaded.sh`

**Step 1: Write the failing test**

Create `tests/unit/test-instructions-loaded.sh` to verify:
- missing referenced file produces a warning context
- valid referenced file allows without noise

Use a simple fixture-driven check around `file_path` from hook input.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-instructions-loaded.sh --verbose
```

Expected: FAIL because the hook does not exist.

**Step 3: Write minimal implementation**

Create `hooks/instructions-loaded` so it:
- reads `file_path` from stdin JSON
- warns when the plugin references a missing internal file
- emits allow JSON in all normal cases

Keep it non-blocking.

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-instructions-loaded.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add hooks/instructions-loaded tests/unit/test-instructions-loaded.sh
git commit -m "feat: add instructions consistency warnings"
```

---

### Task 7: Refactor `SessionStart` onto the shared helper layer

**Files:**
- Modify: `hooks/session-start`
- Test: `tests/unit/test-session-output.sh`
- Test: `tests/unit/test-hook-properties.sh`
- Test: `tests/unit/test-json-escaping.sh`

**Step 1: Write the failing test**

Add one assertion to `tests/unit/test-session-output.sh` that requires `SessionStart` to keep producing both:
- `additional_context`
- `hookSpecificOutput.additionalContext`

Add one assertion to `tests/unit/test-hook-properties.sh` requiring exit code `0` and identical output across runs after the refactor.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --unit --test test-session-output.sh --verbose
bash tests/run-all.sh --unit --test test-hook-properties.sh --verbose
```

Expected: FAIL once the new assertions are in place and before the refactor is complete.

**Step 3: Write minimal implementation**

Refactor `hooks/session-start` to source the shared helpers while preserving current behavior:
- repo detection stays unchanged unless covered by tests
- JSON escaping remains compatible with current output
- existing injected context text remains semantically intact

**Step 4: Run test to verify it passes**

Run:

```bash
bash tests/run-all.sh --unit --test test-session-output.sh --verbose
bash tests/run-all.sh --unit --test test-hook-properties.sh --verbose
bash tests/run-all.sh --unit --test test-json-escaping.sh --verbose
```

Expected: PASS.

**Step 5: Commit**

```bash
git add hooks/session-start tests/unit/test-session-output.sh tests/unit/test-hook-properties.sh tests/unit/test-json-escaping.sh
git commit -m "refactor: move session-start onto shared hook helpers"
```

---

### Task 8: Add critical integration tests and update docs

**Files:**
- Create: `tests/integration/test-config-change-block.sh`
- Create: `tests/integration/test-task-completed-enforcement.sh`
- Modify: `README.md`

**Step 1: Write the failing tests**

Create integration tests for:
- invalid config change is blocked
- task completion is rejected before verification and allowed after verification

Keep them focused and re-use `tests/helpers.sh`.

**Step 2: Run test to verify it fails**

Run:

```bash
bash tests/run-all.sh --integration --test test-config-change-block.sh --verbose
bash tests/run-all.sh --integration --test test-task-completed-enforcement.sh --verbose
```

Expected: FAIL because the behavior is not fully implemented yet.

**Step 3: Write minimal implementation and docs**

Update `README.md` with:
- supported hook set
- what blocks vs what only warns
- default verification command
- unit vs integration test commands

**Step 4: Run full verification**

Run:

```bash
bash tests/run-all.sh --unit --verbose
bash tests/run-all.sh --integration --verbose
```

Expected: all targeted tests PASS.

**Step 5: Commit**

```bash
git add README.md tests/integration/test-config-change-block.sh tests/integration/test-task-completed-enforcement.sh
git commit -m "test: cover critical enforcement flows end to end"
```
