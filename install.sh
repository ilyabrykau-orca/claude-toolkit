#!/usr/bin/env bash
# claude-toolkit installer — fresh install or upgrade
# Usage: bash install.sh [--force]
#
# What it does:
#   1. Adds orca-sensor-marketplace (if missing)
#   2. Installs/updates claude-toolkit plugin
#   3. Creates Serena project configs (.serena/project.yml) with proper ignores
#   4. Creates .cbmignore files for codebase-memory-mcp
#   5. Creates .mcp.json for codebase-memory-mcp server
#   6. Creates .claude/settings.local.json for project settings
#   7. Migrates v1 (Codanna) → v2 (cbm) if old configs detected
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MARKETPLACE_NAME="orca-sensor-marketplace"
MARKETPLACE_REPO="ilyabrykau-orca/orca-sensor-marketplace"
PLUGIN_NAME="claude-toolkit"
PLUGIN_FULL="${PLUGIN_NAME}@${MARKETPLACE_NAME}"

# Workspace root — default to ~/src
WORKSPACE="${ORCA_WORKSPACE:-$HOME/src}"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[info]${NC} $*"; }
ok()    { echo -e "${GREEN}[ok]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }
err()   { echo -e "${RED}[error]${NC} $*" >&2; }
step()  { echo -e "\n${GREEN}▶${NC} $*"; }

FORCE="${1:-}"

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
step "Checking prerequisites"

if ! command -v claude &>/dev/null; then
    err "Claude Code CLI not found. Install from: https://claude.ai/code"
    exit 1
fi
ok "Claude Code CLI found"

if ! command -v jq &>/dev/null; then
    err "jq not found. Install: brew install jq"
    exit 1
fi
ok "jq found"

if ! command -v node &>/dev/null; then
    warn "node not found — session analytics hooks won't work (optional)"
fi

if [ ! -d "$WORKSPACE" ]; then
    err "Workspace not found at $WORKSPACE. Set ORCA_WORKSPACE env var."
    exit 1
fi
ok "Workspace: $WORKSPACE"

# ---------------------------------------------------------------------------
# Step 1: Marketplace
# ---------------------------------------------------------------------------
step "Setting up marketplace"

KNOWN_MP="$HOME/.claude/plugins/known_marketplaces.json"
if [ -f "$KNOWN_MP" ] && jq -e ".\"$MARKETPLACE_NAME\"" "$KNOWN_MP" &>/dev/null; then
    ok "Marketplace '$MARKETPLACE_NAME' already registered"
else
    info "Adding marketplace: $MARKETPLACE_REPO"
    claude plugin marketplace add "$MARKETPLACE_REPO" 2>&1 || {
        err "Failed to add marketplace. Add manually: claude plugin marketplace add $MARKETPLACE_REPO"
        exit 1
    }
    ok "Marketplace added"
fi

# ---------------------------------------------------------------------------
# Step 2: Plugin install/update
# ---------------------------------------------------------------------------
step "Installing/updating plugin"

INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
if [ -f "$INSTALLED_JSON" ] && jq -e ".plugins.\"$PLUGIN_FULL\"" "$INSTALLED_JSON" &>/dev/null; then
    info "Plugin already installed, checking for updates..."
    claude plugin update "$PLUGIN_FULL" 2>&1
else
    info "Installing $PLUGIN_FULL..."
    claude plugin install "$PLUGIN_FULL" 2>&1 || {
        err "Failed to install plugin. Try: claude plugin install $PLUGIN_FULL"
        exit 1
    }
fi
ok "Plugin ready"

# ---------------------------------------------------------------------------
# Step 3: Serena project configs
# ---------------------------------------------------------------------------
step "Setting up Serena project configs"

# Detect which repos exist
REPOS=()
[ -d "$WORKSPACE/orca" ] && REPOS+=("orca")
[ -d "$WORKSPACE/orca-sensor" ] && REPOS+=("orca-sensor")
[ -d "$WORKSPACE/orca-runtime-sensor" ] && REPOS+=("orca-runtime-sensor")

create_serena_project() {
    local repo_path="$1"
    local project_name="$2"
    local languages="$3"
    local ignored_paths="$4"
    local serena_dir="$repo_path/.serena"
    local yml="$serena_dir/project.yml"

    if [ -f "$yml" ] && [ "$FORCE" != "--force" ]; then
        ok "  $project_name: .serena/project.yml exists (use --force to overwrite)"
        return
    fi

    mkdir -p "$serena_dir"

    cat > "$yml" << YAMLEOF
languages:
$languages

encoding: "utf-8"
ignore_all_files_in_gitignore: true

ignored_paths:
$ignored_paths

read_only: false
excluded_tools: []
initial_prompt: ""
project_name: "$project_name"
included_optional_tools: []
base_modes:
default_modes:
fixed_tools: []
YAMLEOF

    # Ensure .serena/.gitignore exists
    if [ ! -f "$serena_dir/.gitignore" ]; then
        cat > "$serena_dir/.gitignore" << 'GIEOF'
cache/
*.pkl
GIEOF
    fi

    ok "  $project_name: created .serena/project.yml"
}

# orca-unified (workspace root)
create_serena_project "$WORKSPACE" "orca-unified" \
"- python
- go
- cpp
- bash
- terraform
- yaml
- markdown" \
'- flow/
- helm-charts/
- grafana-provisioning/
- orca-cloud-platform/
- logs/
- docs/
- "**/.venv/"
- "**/node_modules/"
- "**/out/"
- "**/__pycache__/"
- "**/.**"'

# Individual repos
for repo in "${REPOS[@]}"; do
    case "$repo" in
        orca)
            create_serena_project "$WORKSPACE/$repo" "$repo" \
"- python
- typescript
- go
- yaml
- markdown" \
'- "**/__pycache__/**"
- "**/node_modules/**"
- "**/.venv/**"
- "**/dist/**"
- "**/build/**"'
            ;;
        orca-sensor)
            create_serena_project "$WORKSPACE/$repo" "$repo" \
"- go
- terraform
- yaml
- markdown" \
'[]'
            ;;
        orca-runtime-sensor)
            create_serena_project "$WORKSPACE/$repo" "$repo" \
"- go
- cpp
- terraform
- yaml
- markdown" \
'[]'
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Step 4: .cbmignore files
# ---------------------------------------------------------------------------
step "Setting up .cbmignore files"

create_cbmignore() {
    local path="$1"
    local content="$2"
    if [ -f "$path" ] && [ "$FORCE" != "--force" ]; then
        ok "  $(basename "$(dirname "$path")"): .cbmignore exists (use --force to overwrite)"
        return
    fi
    echo "$content" > "$path"
    ok "  $(basename "$(dirname "$path")"): created .cbmignore"
}

# Workspace root
create_cbmignore "$WORKSPACE/.cbmignore" "# Unified workspace: only index the three main repos
/helm-charts/
/grafana-provisioning/
/orca-cloud-platform/
/logs/
/docs/
/.*"

# orca
[ -d "$WORKSPACE/orca" ] && create_cbmignore "$WORKSPACE/orca/.cbmignore" \
"# codebase-memory-mcp ignore — orca
# Target: ~8K source files. Skip data, fixtures, generated, caches.

# Virtual environments & caches
.venv/
venv/
.*_cache/
__pycache__/
*.egg-info/
.*-cache/
.git/
.serena/

# Build artifacts
target/
build/
dist/
*.o
*.so
*.dylib

# Bulk data dirs
broots/
external_dockers/
lib/orca/alert_rules/
lib/orca/dynamic_updates/
utils/cis_frameworks/

# CIS test data (17K files, only 113 actual .py)
sensors/services/cdi/

# Test data & fixtures
**/tests/account*data*/
**/tests/stubs/
**/__snapshots__/
system_tests/

# Django migrations (auto-generated)
**/migrations/

# Dependencies
node_modules/
vendor/
.cargo/

# Generated
*.generated.*
*.auto.*
*_pb2.py
*.pb.go

# IDE / VCS / hidden
.idea/
.vscode/
.cursor/
.git/
.github/
.svn/
.swm/
.DS_Store

# Non-code files cbm doesn't need to parse
*.md
*.xml
*.html
*.csv
*.txt
*.sql
*.conf
*.secret
*.tfvars
*.tpl
*.json

# Temp
*.tmp
*.temp
*.bak
*.swp
*~"

# orca-sensor
[ -d "$WORKSPACE/orca-sensor" ] && create_cbmignore "$WORKSPACE/orca-sensor/.cbmignore" \
"# codebase-memory-mcp ignore — orca-sensor
vendor/
.git/
.github/
.idea/
.orca_state/
.serena/
docs/
*.md
*.sql
*.xml
*.tfvars
*.hcl
*.json"

# orca-runtime-sensor
[ -d "$WORKSPACE/orca-runtime-sensor" ] && create_cbmignore "$WORKSPACE/orca-runtime-sensor/.cbmignore" \
"# codebase-memory-mcp ignore — orca-runtime-sensor

# Bundled Python env (6K+ files)
scripts/python/

# Git worktrees
.worktrees/

# Standard ignores
vendor/
.git/
.github/
.serena/
__pycache__/
*.pyc
*.gz
*.md
*.json
*.txt"

# ---------------------------------------------------------------------------
# Step 5: .mcp.json for codebase-memory-mcp
# ---------------------------------------------------------------------------
step "Setting up MCP server config"

MCP_JSON="$WORKSPACE/.mcp.json"
if [ -f "$MCP_JSON" ] && jq -e '.mcpServers."codebase-memory-mcp"' "$MCP_JSON" &>/dev/null; then
    ok "codebase-memory-mcp already in .mcp.json"
elif [ -f "$MCP_JSON" ]; then
    # Merge into existing .mcp.json
    info "Adding codebase-memory-mcp to existing .mcp.json"
    jq '.mcpServers["codebase-memory-mcp"] = {
        "command": "npx",
        "args": ["-y", "codebase-memory-mcp"],
        "type": "stdio"
    }' "$MCP_JSON" > "${MCP_JSON}.tmp" && mv "${MCP_JSON}.tmp" "$MCP_JSON"
    ok "Added codebase-memory-mcp to .mcp.json"
else
    info "Creating .mcp.json"
    cat > "$MCP_JSON" << 'MCPEOF'
{
  "mcpServers": {
    "codebase-memory-mcp": {
      "command": "npx",
      "args": ["-y", "codebase-memory-mcp"],
      "type": "stdio"
    }
  }
}
MCPEOF
    ok "Created .mcp.json with codebase-memory-mcp"
fi

# ---------------------------------------------------------------------------
# Step 6: .claude/settings.local.json
# ---------------------------------------------------------------------------
step "Setting up Claude Code project settings"

CLAUDE_DIR="$WORKSPACE/.claude"
LOCAL_SETTINGS="$CLAUDE_DIR/settings.local.json"
mkdir -p "$CLAUDE_DIR"

if [ -f "$LOCAL_SETTINGS" ] && [ "$FORCE" != "--force" ]; then
    # Ensure enabledMcpjsonServers includes cbm
    if jq -e '.enabledMcpjsonServers | index("codebase-memory-mcp")' "$LOCAL_SETTINGS" &>/dev/null; then
        ok "settings.local.json already configured"
    else
        info "Adding codebase-memory-mcp to enabledMcpjsonServers"
        jq '.enabledMcpjsonServers = (.enabledMcpjsonServers // []) + ["codebase-memory-mcp"] | .enabledMcpjsonServers |= unique' \
            "$LOCAL_SETTINGS" > "${LOCAL_SETTINGS}.tmp" && mv "${LOCAL_SETTINGS}.tmp" "$LOCAL_SETTINGS"
        ok "Updated settings.local.json"
    fi
else
    cat > "$LOCAL_SETTINGS" << 'SETTEOF'
{
  "enabledMcpjsonServers": [
    "codebase-memory-mcp"
  ],
  "enableAllProjectMcpServers": true
}
SETTEOF
    ok "Created settings.local.json"
fi

# ---------------------------------------------------------------------------
# Step 7: v1 → v2 migration (detect and clean Codanna leftovers)
# ---------------------------------------------------------------------------
step "Checking for v1 (Codanna) leftovers"

migrated=0

# Check for Codanna references in .mcp.json
if [ -f "$MCP_JSON" ] && jq -e '.mcpServers.codanna // .mcpServers.Codanna' "$MCP_JSON" &>/dev/null; then
    warn "Found Codanna server in .mcp.json — removing"
    jq 'del(.mcpServers.codanna) | del(.mcpServers.Codanna)' "$MCP_JSON" > "${MCP_JSON}.tmp" && mv "${MCP_JSON}.tmp" "$MCP_JSON"
    migrated=1
fi

# Check for .codanna directories
for d in "$WORKSPACE" "$WORKSPACE"/orca "$WORKSPACE"/orca-sensor "$WORKSPACE"/orca-runtime-sensor; do
    if [ -d "$d/.codanna" ]; then
        warn "Found .codanna/ in $d — you can safely remove it: rm -rf $d/.codanna"
        migrated=1
    fi
done

# Check Serena memories for Codanna references
for d in "$WORKSPACE" "$WORKSPACE"/orca "$WORKSPACE"/orca-sensor "$WORKSPACE"/orca-runtime-sensor; do
    mem_dir="$d/.serena/memories"
    if [ -d "$mem_dir" ]; then
        codanna_refs=$(grep -ril "codanna" "$mem_dir" 2>/dev/null || true)
        if [ -n "$codanna_refs" ]; then
            warn "Serena memories with Codanna references in $d/.serena/memories/:"
            echo "$codanna_refs" | while read -r f; do echo "  - $(basename "$f")"; done
            warn "Review and update these memories to reference codebase-memory-mcp instead"
            migrated=1
        fi
    fi
done

if [ $migrated -eq 0 ]; then
    ok "No v1 (Codanna) leftovers found"
else
    warn "Migration items found above — review and clean up manually"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  claude-toolkit setup complete!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Restart Claude Code to apply plugin changes."
echo ""
echo "  What was set up:"
echo "    ✓ Marketplace: $MARKETPLACE_NAME"
echo "    ✓ Plugin: $PLUGIN_FULL"
echo "    ✓ Serena configs: .serena/project.yml (per repo)"
echo "    ✓ CBM ignores: .cbmignore (per repo)"
echo "    ✓ MCP server: codebase-memory-mcp in .mcp.json"
echo "    ✓ Project settings: .claude/settings.local.json"
echo ""
echo "  Quick start:"
echo "    cd $WORKSPACE && claude"
echo ""
echo "  First session will auto-detect the workspace and activate tools."
echo ""
