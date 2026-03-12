---
name: orca-setup
description: Orca workspace setup — tool routing enforcement, codebase-memory-mcp/RTK/Serena patterns, memory protocol.
---

# Orca Workspace Setup

## TOOL ENFORCEMENT ACTIVE

Native `Read`, `Edit`, `Write`, `Grep`, `Glob` are **HARD-BLOCKED** on code files (.py, .go, .ts, .tsx, .js, .jsx, .rs, .cpp, .c, .h, .hpp, .rb, .java).
A PreToolUse hook returns exit 2 if you attempt to use them. Use MCP tools instead.

Non-code files (.json, .yaml, .md, .toml, .cfg, .sh, Makefile, Dockerfile) → native tools allowed.

Shell commands (git, pytest, go test, make, etc.) go through **RTK global rewrite** for token compression — always use native Bash for shell.

---

## Step 1: Activate Project

Execute immediately:

```
mcp__serena__activate_project(project=<detected-project>)
```

Then load memories:

```
codebase-memory-mcp manage_adr(action="list")
codebase-memory-mcp manage_adr(action="get", id="cross_project_map")
```

---

## Step 2: Tool Routing

### Search Code

```python
# Broad "how does X work?" — natural language search
codebase-memory-mcp search_graph(query="how does kafka offset commit work", lang="python", limit=5)

# Exact symbol lookup by name with kind filter
codebase-memory-mcp search_graph(query="AbstractSensor", lang="python", kind="class")

# Fuzzy search with filters
codebase-memory-mcp search_graph(query="sensor", kind="class", lang="python", limit=10)

# Pattern/regex search across files
codebase-memory-mcp search_code(query="TODO|FIXME", glob="**/*.py")
```

### Read Code

```python
# Read symbol with body (preferred — token efficient)
codebase-memory-mcp get_code_snippet(symbol="AbstractSensor", path="orca/sensors/")

# Read file range via RTK (shell passthrough)
rtk read orca/sensors/base.py 10:50
# or via Bash:
# Bash: cat -n orca/sensors/base.py | sed -n '10,50p'
```

### Edit Code — The Golden Loop

1. **Search**: `codebase-memory-mcp search_graph(query="...")`
2. **Locate**: `codebase-memory-mcp search_graph(query="...", lang="...", kind="...")`
3. **Trace**: `codebase-memory-mcp trace_call_path(symbol="TargetFunc", path="orca/module/file.py")` — **MANDATORY before any edit.**
4. **Plan**: TaskCreate with research → implement → verify
5. **Edit**: Serena tools (see below)
6. **Verify**: `pytest` / `go test`

### Edit Tools

```python
# Replace entire function/class (safest)
mcp__serena__replace_symbol_body(
    name_path="MyClass/process_data",
    relative_path="orca/sensors/processor.py",
    body="def process_data(self, event):\n    return self.transform(event)"
)

# Targeted literal edit
mcp__serena__replace_content(
    relative_path="orca/config.py",
    needle="TIMEOUT = 30",
    repl="TIMEOUT = 60",
    mode="literal"
)

# Regex edit — backreferences use $!1, $!2 (NOT \1, \2)
mcp__serena__replace_content(
    relative_path="orca/sensors/base.py",
    needle="log\\(\"(.*?)\"\\)",
    repl="logger.info(\"$!1\")",
    mode="regex"
)

# Insert after existing symbol
mcp__serena__insert_after_symbol(
    name_path="existing_function",
    relative_path="orca/utils.py",
    body="\ndef new_function():\n    pass"
)
```

### Call Graph

```python
# Who calls this / what does this call — trace in both directions
codebase-memory-mcp trace_call_path(symbol="process_event", direction="callers")
codebase-memory-mcp trace_call_path(symbol="handle_request", direction="callees")

# Full impact before risky refactor
codebase-memory-mcp detect_changes(symbol="SensorBase", max_depth=3)
```

### Library Documentation

```python
mcp__docs__search_docs(library="fastapi", query="dependency injection", limit=5)
mcp__docs__fetch_url(url="https://docs.example.com/api")
```

---

## Step 3: Memory Protocol

At session start: `codebase-memory-mcp manage_adr(action="list")` → read relevant ones.

```python
codebase-memory-mcp manage_adr(
    action="create",
    id="kafka_migration",
    content="# Kafka Migration\n\nDecision: use confluent-kafka..."
)
codebase-memory-mcp manage_adr(action="get", id="cross_project_map")
```

---

## Projects

| Project | Path | Language |
|---------|------|----------|
| orca | ~/src/orca | Python/Django |
| orca-sensor | ~/src/orca-sensor | Go |
| orca-runtime-sensor | ~/src/orca-runtime-sensor | Go+eBPF |
| orca-unified | ~/src | Python+Go (multi-repo) |
| helm-charts | ~/src/helm-charts | YAML |

---

## Params Cheat Sheet

Copy-paste correct parameter names. No aliases work.

| Tool | Param | Correct | WRONG (do not use) |
|------|-------|---------|---------------------|
| `search_graph` (cbm) | language | `lang` | `language` |
| `search_graph` (cbm) | symbol kind | `kind` | `type`, `symbol_type` |
| `trace_call_path` (cbm) | symbol | `symbol` | `function_name`, `symbol_id` |
| `detect_changes` (cbm) | symbol | `symbol` | `symbol_name`, `symbol_id` |
| `manage_adr` (cbm) | action values | `"list"`, `"get"`, `"create"` | `"read"`, `"write"` |
| `find_referencing_symbols` | symbol | `name_path` + `relative_path` (FILE) | `symbol_name`, dir path |
| `replace_content` | params | `needle`, `repl`, `mode` | `pattern`, `replacement`, `is_regex` |
| `replace_content` | mode values | `"literal"` or `"regex"` | `True`, `false`, `"regexp"` |
| `replace_content` | backrefs | `$!1`, `$!2` | `\1`, `\2` |
| `find_symbol` (Serena) | symbol | `name_path_pattern` | `name`, `symbol_name` |
| `read_file` | lines | 0-based, `end_line` inclusive | 1-based |

---

## Verification

Show actual command output before claiming done:
- Python: `pytest <path> -v`
- Go: `go test ./...`
- Lint: `ruff check .` / `golangci-lint run`
