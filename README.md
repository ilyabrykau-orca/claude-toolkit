# claude-toolkit

Claude Code plugin that enforces MCP tool routing for codebases using [codebase-memory-mcp](https://github.com/nicobailon/codebase-memory-mcp) and [Serena](https://github.com/aorwall/serena).

Instead of letting Claude use native Read/Edit/Grep on code files, this plugin blocks them and routes to MCP-powered alternatives — giving you semantic search, symbolic editing, reference tracking, and impact analysis.

## What it does

| Native tool | Blocked on | Routed to |
|---|---|---|
| `Read` | Code files (.py, .go, .ts, .rs, ...) | `codebase-memory-mcp get_code_snippet` / `rtk read` |
| `Edit` / `Write` | Code files | `mcp__serena__replace_symbol_body` / `mcp__serena__replace_content` |
| `Grep` | All files | `mcp__codebase-memory-mcp__search_code` |
| `Glob` | All files | `mcp__codebase-memory-mcp__search_graph` |

Non-code files (.json, .yaml, .md, .toml) pass through to native tools.

### Additional features

- **Edit guard** — warns if you edit code without first calling `codebase-memory-mcp trace_call_path` (prevents breaking callers)
- **Project detection** — auto-detects workspace project from cwd, injects Serena activation context
- **Skill activation** — suggests relevant skills (codebase-memory, serena-workflow, docs) based on prompt keywords
- **Session analytics** — tracks token usage, tool distribution, and costs per session

## Prerequisites

- [Claude Code](https://claude.ai/code) CLI installed
- [codebase-memory-mcp](https://github.com/nicobailon/codebase-memory-mcp) (stdio transport)
- [Serena](https://github.com/aorwall/serena) running at `http://127.0.0.1:8765/mcp`
- `jq` installed (`brew install jq`)

## Install

### Automated (recommended)

```bash
git clone git@github.com:ilyabrykau-orca/claude-toolkit.git /tmp/claude-toolkit
bash /tmp/claude-toolkit/install.sh
```

This sets up everything: marketplace, plugin, Serena configs, `.cbmignore` files, `.mcp.json`, and project settings. Run with `--force` to overwrite existing configs.

If upgrading from v1 (Codanna), the script detects and warns about leftover configs.

### Manual

```bash
# Register marketplace (one-time)
claude plugin marketplace add ilyabrykau-orca/orca-sensor-marketplace

# Install plugin
claude plugin install claude-toolkit@orca-sensor-marketplace
```

## Plugin structure

```
hooks/
  pre-tool-router       ← bash: native blocking + edit guard (~10ms)
  post-cbm-trace        ← bash: tracks cbm trace calls for edit guard
  skill-activation-prompt ← bash: keyword matching for skill suggestions
  session-start         ← bash: project detection + context injection
  stop.js               ← node: session analytics (once per session)
  subagent-stop.js      ← node: subagent analytics
  utils/transcript-parser.js

skills/
  orca-setup/SKILL.md   ← workspace routing rules, build commands
  serena-workflow/SKILL.md ← Serena editing protocol
  docs/SKILL.md         ← Docs MCP usage
  skill-rules.json      ← keyword triggers for skill activation

tests/
  test_pre_tool_router.py  ← pre-tool-router hook tests
  test_post_cbm_trace.py   ← post-cbm-trace hook tests
  test_session_start.py    ← session-start pipeline tests

install.sh              ← automated installer (fresh + upgrade)
```

## Hook latency

All PreToolUse hooks run in a single bash process (~8-10ms).
Node.js hooks (stop/subagent-stop) run once per session end.

| Hook | Latency | Frequency |
|---|---|---|
| `pre-tool-router` | ~10ms | Every tool call |
| `post-cbm-trace` | ~12ms | After `trace_call_path` / `search_graph` |
| `skill-activation-prompt` | ~8ms | Per user message |
| `session-start` | ~11ms | Per session |
| `stop.js` | ~70ms | Once at session end |

## Testing

```bash
cd /path/to/claude-toolkit
pip install -r tests/requirements.txt
pytest tests/ -v
```

## Configuration

### Project detection

The `session-start` hook detects the workspace from `$PWD`:

| Path pattern | Detected project |
|---|---|
| `*/orca-runtime-sensor*` | `orca-runtime-sensor` |
| `*/orca-sensor*` | `orca-sensor` |
| `*/helm-charts*` | `helm-charts` |
| `*/src/orca*` | `orca` |
| `*/src` | `orca-unified` |

Edit `hooks/session-start` to add your own projects.

### Blocked file extensions

Edit the `case` pattern in `hooks/pre-tool-router` (line 41):

```bash
*.py|*.go|*.ts|*.tsx|*.js|*.jsx|*.rs|*.cpp|*.c|*.h|*.hpp|*.rb|*.java|*.kt|*.php|*.scala|*.swift|*.sh|*.bash)
```

## License

MIT
