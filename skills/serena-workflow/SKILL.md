---
name: serena-workflow
description: Serena editing workflow — symbol-level editing, replace_content. Use for ALL code editing tasks in orca repos. Search/read via codebase-memory-mcp before editing.
---

# Serena Editing Workflow

Native Edit/Write are HARD-BLOCKED on code files. Use Serena for all code editing.

## Mandatory Pre-Edit Checklist

Before ANY code edit:
1. `codebase-memory-mcp trace_call_path(symbol="target_symbol", path="path/to/file.py")` — check all references and call graph
2. Review references — understand impact scope
3. Plan with TaskCreate: research → implement → verify
4. Get user approval

## Edit Tool Selection

| Situation | Tool |
|-----------|------|
| Replace entire function/class/method | `replace_symbol_body` |
| Edit few lines within a larger symbol | `replace_content` |
| Add new code after existing symbol | `insert_after_symbol` |
| Add new code before first symbol | `insert_before_symbol` |
| Rename across whole codebase | `rename_symbol` |

## A. replace_symbol_body

```python
mcp__serena__replace_symbol_body(
    name_path="MyClass/process_data",
    relative_path="orca/sensors/processor.py",
    body="def process_data(self, event):\n    return self.transform(event)"
)
```

Note: `body` is the implementation only — excludes docstrings and leading comments.

## B. replace_content

```python
# Literal replacement (exact string match)
mcp__serena__replace_content(
    relative_path="orca/config.py",
    needle="TIMEOUT = 30",
    repl="TIMEOUT = 60",
    mode="literal"
)

# Regex with wildcards (preferred — avoids quoting full text)
mcp__serena__replace_content(
    relative_path="orca/sensors/base.py",
    needle="def old_method\\(self\\).*?return result",
    repl="def new_method(self):\n    return self.compute()",
    mode="regex"
)

# Regex with backreferences — use $!1, $!2 (NOT \1, \2)
mcp__serena__replace_content(
    relative_path="orca/utils.py",
    needle="log\\(\"(.*?)\"\\)",
    repl="logger.info(\"$!1\")",
    mode="regex"
)
```

## C. Insert Code

```python
# After an existing symbol
mcp__serena__insert_after_symbol(
    name_path="existing_function",
    relative_path="orca/utils.py",
    body="\ndef new_function():\n    pass"
)

# Before an existing symbol (e.g. add imports at top of file)
mcp__serena__insert_before_symbol(
    name_path="first_class",
    relative_path="orca/models.py",
    body="import logging\n\nlogger = logging.getLogger(__name__)\n"
)
```

## D. Rename Across Codebase

```python
mcp__serena__rename_symbol(
    name_path="OldClassName",
    relative_path="orca/models.py",
    new_name="NewClassName"
)
```

## Key Gotchas

| Gotcha | Rule |
|--------|------|
| Pre-edit reference check | Use `codebase-memory-mcp trace_call_path` — NOT `find_referencing_symbols` |
| `replace_content` backrefs | `$!1`, `$!2` — NOT `\1`, `\2` |
| `replace_symbol_body` body | Implementation only — no docstrings/comments |
| `mode` values | Exactly `"literal"` or `"regex"` (lowercase) |
| `find_symbol` param | `name_path_pattern` — NOT `name` or `symbol_name` |

## Wrong vs Right

| Wrong | Right |
|-------|-------|
| `find_referencing_symbols(name_path="Foo", ...)` | `codebase-memory-mcp trace_call_path(symbol="Foo", path="orca/file.py")` |
| `replace_content(... mode="regexp")` | `replace_content(... mode="regex")` |
| `replace_content(... repl="\\1 value")` | `replace_content(... repl="$!1 value")` |
| `find_symbol(name="Foo", include_body=True)` | `find_symbol(name_path_pattern="Foo", include_body=True)` |
