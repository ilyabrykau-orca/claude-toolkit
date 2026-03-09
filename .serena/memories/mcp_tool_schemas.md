# MCP Tool Schemas — Verified from Source

## Codanna (v0.9.14)
| Tool | Key Params |
|------|-----------|
| find_symbol | name, symbol_id, lang, kind, include_body, depth |
| search_symbols | query, lang, kind, module, limit, substring_matching |
| get_calls | function_name OR symbol_id |
| find_callers | function_name OR symbol_id |
| analyze_impact | symbol_name OR symbol_id, max_depth (default 3) |
| semantic_search_with_context | query, lang, limit (default 5), threshold (default 0.60) |
| semantic_search_docs | query, lang, limit, threshold |
| search_documents | query, collection, limit |
| get_index_info | (no params) |

Note: Use symbol_id for unambiguous lookups after disambiguation.

## Serena
| Tool | Key Params |
|------|-----------|
| find_symbol | name_path_pattern, depth, relative_path, include_body, include_info |
| find_referencing_symbols | name_path, relative_path (FILE only!) |
| replace_symbol_body | name_path, relative_path, body (excludes docstrings) |
| replace_content | relative_path, needle, repl, mode ("literal"/"regex"), allow_multiple_occurrences |
| insert_after_symbol | name_path, relative_path, body |
| insert_before_symbol | name_path, relative_path, body |
| rename_symbol | name_path, relative_path, new_name |
| read_file | relative_path, start_line (0-based), end_line (0-based inclusive) |
| get_symbols_overview | relative_path, depth |
| search_for_pattern | substring_pattern (regex), paths_include_glob, relative_path |
| activate_project | project (name or path) |
| write_memory | memory_name (supports "/" hierarchy), content |
| read_memory | memory_name |
| list_memories | topic (optional prefix filter) |

Critical: replace_content backreferences use $!1 $!2 NOT \1 \2

## Docs MCP (v2.0.4)
| Tool | Key Params |
|------|-----------|
| search_docs | library, query, version (optional), limit (default 5) |
| scrape_docs | library, url, version, options.maxPages/maxDepth/scope |
| fetch_url | url, followRedirects, scrapeMode (fetch/playwright/auto) |
| list_libraries | (no params) |
| find_version | library, targetVersion |

## PreToolUse Hook (Claude Code Official)
- Exit 2 = block tool, stderr shown to Claude
- JSON: hookSpecificOutput.permissionDecision = "deny" + permissionDecisionReason
- Input stdin: { tool_name, tool_input, session_id, cwd, ... }
- Claude Code native tools: Read, Edit, Write, Grep, Glob
