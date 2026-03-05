---
name: codanna
description: Use when you need detailed guidance on Codanna MCP tool query patterns, understanding what each tool does, or troubleshooting Codanna searches. Covers all 8 Codanna tools with examples.
---

# Codanna Code Intelligence

Codanna indexes your entire workspace: orca, orca-sensor, orca-runtime-sensor, helm-charts.
Index at: `/Users/ilyabrykau/src/.codanna/`

## Tool Reference

| Tool | Purpose | When |
|------|---------|------|
| `semantic_search_with_context` | NL search + callers + calls | "How does X work?" |
| `find_symbol` | Exact name lookup | "Where is class Foo?" |
| `search_symbols` | Fuzzy + kind/lang filter | Partial name or type |
| `find_callers` | Who calls this? | Upstream dependencies |
| `get_calls` | What does this call? | Downstream dependencies |
| `analyze_impact` | Full dependency graph | Before risky changes |
| `semantic_search_docs` | NL search in markdown | Architecture docs |
| `search_documents` | Keyword search in docs | Known term in docs |

## Query Examples

```python
# Find class by name
mcp__codanna__find_symbol(name="AbstractSensor", language="python")

# Find Go interface
mcp__codanna__find_symbol(name="SensorAgent", language="go")

# Broad concept search
mcp__codanna__semantic_search_with_context(query="kafka consumer group handling")

# Fuzzy search, classes only
mcp__codanna__search_symbols(query="sensor", kind="class", language="python")

# Who calls this function?
mcp__codanna__find_callers(symbol_id="<id from find_symbol>")

# What does this function call?
mcp__codanna__get_calls(symbol_id="<id>", depth=2)

# Impact before editing
mcp__codanna__analyze_impact(symbol_id="<id>")

# Search orca docs
mcp__codanna__semantic_search_docs(query="how does asset scanning work")
```
