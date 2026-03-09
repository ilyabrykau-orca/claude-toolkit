# Claude Enforcement Reliability Design

**Date:** 2026-03-06

## Goal

Revise `orca-env-plugin` into a Claude-only workflow enforcement plugin that improves reliability through deterministic hooks, explicit verification gates, and testable policy logic.

## Scope

In scope:
- Claude Code plugin behavior only
- deterministic command hooks
- tool-routing guidance at session start
- blocking validation for high-confidence failures
- unit and integration coverage for every blocking rule

Out of scope for this revision:
- Codex support
- prompt hooks
- agent hooks
- broad `Stop` enforcement
- heuristic blocking based on model judgment

## Architecture

The plugin should use a thin-hook architecture:

- `hooks/hooks.json`: event wiring only
- `hooks/<event>`: small event adapters
- `lib/*.sh`: shared helpers for JSON parsing, output shaping, path validation, policy loading, and repo detection
- `policies/*`: explicit deterministic rules that hooks consume
- `tests/unit/*`: fast script and policy tests
- `tests/integration/*`: real Claude CLI behavior tests for critical flows

Design rules:
- shell remains the hook entrypoint runtime
- blocking decisions must be deterministic and explainable
- noncritical failures degrade to allow plus warning
- critical config and verification failures block
- prompt text is guidance, not the enforcement source of truth

## Hook Set

### `SessionStart`

Responsibility:
- detect project from `cwd`
- inject tool-routing and setup guidance
- preserve current Serena/Codanna activation workflow

Blocking:
- never blocks

### `InstructionsLoaded`

Responsibility:
- validate that referenced plugin guidance artifacts exist and are readable
- surface broken internal references early

Blocking:
- warn by default
- only block if the plugin itself is malformed and cannot provide safe guidance

### `PreToolUse`

Responsibility:
- prevent a small set of deterministic bad actions before execution

Initial blockable checks:
- destructive shell banlist if enabled
- protected config or hook file operations that violate policy
- narrowly defined forbidden tool/path combinations where the plugin can decide with high confidence

Blocking:
- yes, but only for deterministic rules

### `ConfigChange`

Responsibility:
- validate changed Claude hook/config payloads before they take effect

Required checks:
- JSON parses
- hook schema is structurally valid
- referenced scripts exist
- referenced scripts are executable when required
- event names and required fields match supported usage

Blocking:
- yes

### `TaskCompleted`

Responsibility:
- enforce verification-before-completion

Required checks:
- identify changed files relevant to the task
- map those files to required verification commands
- require a successful verification result after the relevant edits

Blocking:
- yes

### Supporting `PostToolUse`

Responsibility:
- record successful verification command executions for later `TaskCompleted` checks

Blocking:
- never blocks
- exists only as a deterministic state recorder, not as a broad policy surface

## Enforcement Policy

Hard-block only:
- invalid config or hook changes
- missing required verification for task completion
- deterministic protected-file violations
- explicit shell/tool banlist matches

Warn only:
- likely but nondeterministic tool misuse
- likely skipped research flow
- weaker style/process violations

## Verification Model

Verification must be scriptable and attributable to the changed area.

Initial policy:
- changes under `hooks/`, `skills/`, `commands/`, `tests/`: require `bash tests/run-all.sh --unit`
- changes to hook wiring or plugin metadata: require config validation plus unit tests
- integration tests are required for release-critical behavior and for changes that alter Claude CLI interaction contracts

Task completion should only be blocked when:
- a required verification command is known
- that command has not passed in the current session after the relevant edits
- verification evidence may be derived either from the session transcript or from a narrow `PostToolUse` recorder hook

## Testing Strategy

### Unit coverage

Add dedicated tests for each new blocking hook:
- `tests/unit/test-pre-tool-use.sh`
- `tests/unit/test-config-change.sh`
- `tests/unit/test-task-completed.sh`
- `tests/unit/test-instructions-loaded.sh`

Add helper and policy fixture coverage for:
- malformed JSON
- missing referenced scripts
- protected file edits
- verification missing
- verification passed
- output contract correctness

### Integration coverage

Keep integration tests focused on the critical end-to-end flows:
- `SessionStart` context injection still works
- `ConfigChange` blocks invalid config updates
- `TaskCompleted` blocks completion until verification passes

## Reliability Principles

- no blocking rule should rely on model judgment
- every blocking rule must have unit coverage
- critical user-visible flows must have integration coverage
- hook output must stay machine-readable and quiet on success
- existing `SessionStart` behavior must remain backward-compatible

## Deferred Work

Deliberately deferred from this version:
- `Stop` hook enforcement
- prompt or agent hook evaluators
- Codex-specific integration
- broad cross-repo policy rollout

## Success Criteria

This revision is successful when:
- broken config changes are blocked before activation
- tasks cannot be completed without required verification
- current setup injection still works
- all blocking rules are covered by unit tests
- critical Claude flows are covered by integration tests
- the plugin remains shell-first and dependency-light
