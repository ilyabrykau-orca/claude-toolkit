---
name: orca-setup
description: Orca workspace setup — tool routing, Serena/Codanna patterns, memory protocol. Auto-injected at session start.
---

# Orca Workspace Setup

You are working in the orca multi-repo workspace. This skill is injected automatically at every session start.

## Auto-Activation (Already Done)

The `session-start` hook has already determined your project from `$PWD` and provided an activation command above. Execute it immediately:

```
mcp__serena__activate_project(project=<detected-project>)
```

After activation, read relevant memories:
```
mcp__serena__list_memories()
→ mcp__serena__read_memory(memory_file=<relevant>.md)  # for each relevant memory
```

## Tool Routing (MANDATORY)

For ALL code files (.py, .go, .ts, .tsx, .js, .jsx, .rs, .cpp, .c, .h, .rb, .sh):

| Task | Use This Chain |
|------|---------------|
| Search / understand | `mcp__codanna__semantic_search_with_context` → `mcp__codanna__find_symbol` → `mcp__serena__search_for_pattern` |
| Read symbol body | `mcp__codanna__find_symbol` → `mcp__serena__find_symbol(include_body=True)` → `mcp__serena__read_file` |
| Edit code | `mcp__serena__replace_symbol_body` → `mcp__serena__replace_content` → `mcp__serena__insert_after_symbol` |
| Find references | `mcp__serena__find_referencing_symbols` (ALWAYS before any edit) |
| Impact analysis | `mcp__codanna__analyze_impact` |
| Library docs | `mcp__docs__search_docs` → `WebFetch` |

## NEVER / ALWAYS Rules

**NEVER** use native `Read`, `Edit`, `Write`, `Grep`, `Glob` on code files.
Native tools are allowed ONLY for: JSON, YAML, Markdown, config, shell scripts.

**ALWAYS** call `mcp__serena__find_referencing_symbols` before any edit.
**ALWAYS** use `mcp__codanna__semantic_search_with_context` first for broad "how does X work" questions.
**ALWAYS** use `mcp__codanna__find_symbol` for exact name lookups.

## Codanna Query Patterns

```
# Broad concept search
mcp__codanna__semantic_search_with_context(query="how does asset scanning work")

# Exact symbol lookup
mcp__codanna__find_symbol(name="AbstractSensor", language="python")

# Fuzzy search with kind filter
mcp__codanna__search_symbols(query="sensor", kind="class", language="python")

# Call graph
mcp__codanna__get_calls(symbol_id="...", depth=2)
mcp__codanna__find_callers(symbol_id="...")

# Impact before risky change
mcp__codanna__analyze_impact(symbol_id="...")

# Docs search
mcp__codanna__semantic_search_docs(query="kafka consumer configuration")
```

## Serena Editing Protocol

Before ANY edit:
1. `mcp__serena__find_referencing_symbols(symbol_name="...")` — trace all references
2. Plan with TaskCreate: research → implement → verify
3. Get explicit user approval ("go ahead", "proceed", "yes")

Edit tools:
- Replace whole symbol: `mcp__serena__replace_symbol_body`
- Targeted regex edit: `mcp__serena__replace_content`
- Add code: `mcp__serena__insert_after_symbol` / `mcp__serena__insert_before_symbol`
- Codebase-wide rename: `mcp__serena__rename_symbol`

## Memory Protocol

At session start (MANDATORY):
1. `mcp__serena__list_memories()` — see what's available
2. `mcp__serena__read_memory(memory_file="cross_project_map.md")` — always read this one
3. Read any other memories relevant to the current task

At session end (save learnings):
- `mcp__serena__write_memory(...)` for significant decisions, patterns, or architectural insights

## Projects in This Workspace

| Project | Path | Language | Activate With |
|---------|------|----------|---------------|
| orca-unified | /Users/ilyabrykau/src | Python+Go | `orca-unified` |
| orca | /Users/ilyabrykau/src/orca | Python/Django | `orca` |
| orca-sensor | /Users/ilyabrykau/src/orca-sensor | Go | `orca-sensor` |
| orca-runtime-sensor | /Users/ilyabrykau/src/orca-runtime-sensor | Go+eBPF | `orca-runtime-sensor` |
| helm-charts | /Users/ilyabrykau/src/helm-charts | YAML | `helm-charts` |

## Verification Before Claiming Done

Show actual command output before claiming anything works:
- Python: `pytest <path> -v`
- Go: `go test ./...`
- Lint Python: `ruff check .`
- Lint Go: `golangci-lint run`
