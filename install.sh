#!/usr/bin/env bash
# claude-toolkit installer — fresh install or upgrade
# Usage: bash install.sh [--force]
#
# What it does:
#   1. Adds orca-sensor-marketplace (if missing)
#   2. Installs/updates claude-toolkit plugin
#   3. Adds codebase-memory-mcp MCP server via `claude mcp add`
#   4. Creates Serena project configs (.serena/project.yml) with proper ignores
#   5. Creates .cbmignore files for codebase-memory-mcp
#   6. Migrates v1 (Codanna) → v2 (cbm) if old configs detected
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

if claude plugin marketplace list 2>&1 | grep -q "$MARKETPLACE_NAME"; then
    ok "Marketplace '$MARKETPLACE_NAME' already registered"
else
    info "Adding marketplace: $MARKETPLACE_REPO"
    claude plugin marketplace add "$MARKETPLACE_REPO" || {
        err "Failed to add marketplace. Try: claude plugin marketplace add $MARKETPLACE_REPO"
        exit 1
    }
    ok "Marketplace added"
fi

# ---------------------------------------------------------------------------
# Step 2: Plugin install/update
# ---------------------------------------------------------------------------
step "Installing/updating plugin"

if claude plugin list 2>&1 | grep -q "$PLUGIN_NAME.*$MARKETPLACE_NAME"; then
    info "Plugin already installed, checking for updates..."
    claude plugin update "$PLUGIN_FULL" 2>&1
else
    info "Installing $PLUGIN_FULL..."
    claude plugin install "$PLUGIN_FULL" || {
        err "Failed to install plugin. Try: claude plugin install $PLUGIN_FULL"
        exit 1
    }
fi
ok "Plugin ready"

# ---------------------------------------------------------------------------
# Step 3: MCP server (codebase-memory-mcp)
# ---------------------------------------------------------------------------
step "Setting up codebase-memory-mcp MCP server"

if claude mcp list 2>&1 | grep -q "codebase-memory-mcp"; then
    ok "codebase-memory-mcp already configured"
else
    info "Adding codebase-memory-mcp (project scope)..."
    claude mcp add --scope project codebase-memory-mcp -- npx -y codebase-memory-mcp || {
        err "Failed to add MCP server. Try: claude mcp add --scope project codebase-memory-mcp -- npx -y codebase-memory-mcp"
        exit 1
    }
    ok "codebase-memory-mcp added"
fi

# ---------------------------------------------------------------------------
# Step 4: Serena project configs
# ---------------------------------------------------------------------------
step "Setting up Serena project configs"

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
for repo in orca orca-sensor orca-runtime-sensor; do
    [ -d "$WORKSPACE/$repo" ] || continue
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
# Step 5: .cbmignore files
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

create_cbmignore "$WORKSPACE/.cbmignore" "# Unified workspace: only index the three main repos
/helm-charts/
/grafana-provisioning/
/orca-cloud-platform/
/logs/
/docs/
/.*"

[ -d "$WORKSPACE/orca" ] && create_cbmignore "$WORKSPACE/orca/.cbmignore" \
"# codebase-memory-mcp ignore — orca

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

# CIS test data
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

# Non-code files
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
# Step 6: v1 → v2 migration (detect and clean Codanna leftovers)
# ---------------------------------------------------------------------------
step "Checking for v1 (Codanna) leftovers"

migrated=0

# Check for Codanna MCP server
if claude mcp list 2>&1 | grep -qi "codanna"; then
    warn "Found Codanna MCP server — remove it: claude mcp remove codanna"
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
            warn "Serena memories with Codanna references in $mem_dir/:"
            echo "$codanna_refs" | while read -r f; do echo "  - $(basename "$f")"; done
            warn "Review and update these to reference codebase-memory-mcp instead"
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
echo "    ✓ MCP server: codebase-memory-mcp (via claude mcp add)"
echo "    ✓ Serena configs: .serena/project.yml (per repo)"
echo "    ✓ CBM ignores: .cbmignore (per repo)"
echo ""
echo "  Quick start:"
echo "    cd $WORKSPACE && claude"
echo ""
