---
name: serena-workflow
description: Use when doing complex refactoring, multi-file edits, or when you need detailed Serena symbolic editing patterns. Covers find_referencing_symbols, replace_symbol_body, replace_content, and cross-session memory patterns.
---

# Serena Symbolic Editing Workflow

## Mandatory Pre-Edit Checklist

Before ANY code edit:
1. `mcp__serena__find_referencing_symbols(symbol_name="<target>")` — find all call sites
2. Review references — understand impact scope
3. Create task plan (TaskCreate)
4. Get user approval

## Edit Tool Selection

| Situation | Tool |
|-----------|------|
| Replace entire function/class/method | `replace_symbol_body` |
| Edit few lines within a larger symbol | `replace_content` (regex) |
| Add new code after existing symbol | `insert_after_symbol` |
| Add new code before first symbol | `insert_before_symbol` |
| Rename across whole codebase | `rename_symbol` |

## replace_content Usage

```python
# Replace specific line pattern within a file
mcp__serena__replace_content(
    relative_path="orca/base_api/sensors/my_sensor.py",
    needle="def old_method_name\\(",
    repl="def new_method_name(",
    mode="regex"
)

# Replace with wildcards (match anything between)
mcp__serena__replace_content(
    relative_path="...",
    needle="some_var = .*",
    repl="some_var = new_value",
    mode="regex"
)
```

## Memory Patterns

```python
# Write architectural decision
mcp__serena__write_memory(
    memory_file="kafka_migration.md",
    content="# Kafka Migration Notes\n\nDecision: use confluent-kafka not aiokafka because..."
)

# Read at session start
mcp__serena__list_memories()
mcp__serena__read_memory(memory_file="cross_project_map.md")
mcp__serena__read_memory(memory_file="unified_style.md")
```
