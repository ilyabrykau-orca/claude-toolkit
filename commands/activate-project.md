---
name: activate-project
description: Manually activate a Serena project by name. Use when auto-detection got the wrong project or you want to switch projects mid-session.
---

Activate the specified Serena project:

1. Call `mcp__serena__activate_project(project=$ARGUMENTS)`
2. Call `mcp__serena__list_memories()` and read relevant memories for the activated project
3. Confirm activation to the user: "Activated project: $ARGUMENTS. Memories loaded."

Valid projects: `orca`, `orca-sensor`, `orca-runtime-sensor`, `orca-unified`, `helm-charts`
