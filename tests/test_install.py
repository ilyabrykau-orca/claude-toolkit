"""Tests for install.sh — validates the install pipeline.

Tests use a temporary workspace to avoid modifying real configs.
Claude CLI commands are stubbed since they require auth.
"""
import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = PLUGIN_ROOT / "install.sh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_fake_workspace(tmp_path: Path, repos: list[str] | None = None) -> Path:
    """Create a fake ~/src workspace with repo directories."""
    workspace = tmp_path / "src"
    workspace.mkdir()
    for repo in (repos or ["orca", "orca-sensor", "orca-runtime-sensor"]):
        (workspace / repo).mkdir()
    return workspace


def make_stub_bin(tmp_path: Path) -> Path:
    """Create a bin/ dir with stub `claude` and `jq` commands that record calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # jq stub — pass through to real jq for non-CLI tests
    real_jq = subprocess.run(["which", "jq"], capture_output=True, text=True).stdout.strip()
    (bin_dir / "jq").write_text(f"#!/bin/bash\nexec {real_jq} \"$@\"\n")
    (bin_dir / "jq").chmod(0o755)

    # claude stub — records subcommands to a log file, simulates success
    log_file = tmp_path / "claude_calls.log"
    (bin_dir / "claude").write_text(textwrap.dedent(f"""\
        #!/bin/bash
        echo "$@" >> "{log_file}"
        case "$1 $2" in
            "plugin marketplace")
                case "$3" in
                    list) echo "orca-sensor-marketplace" ;;
                    add)  echo "Marketplace added" ;;
                esac
                ;;
            "plugin list")
                echo "claude-toolkit@orca-sensor-marketplace  2.1.0  user" ;;
            "plugin update")
                echo "claude-toolkit is already at the latest version (2.1.0)." ;;
            "plugin install")
                echo "Plugin installed." ;;
            "mcp list")
                echo "codebase-memory-mcp: npx -y codebase-memory-mcp" ;;
            "mcp add")
                echo "Added MCP server" ;;
        esac
        exit 0
    """))
    (bin_dir / "claude").chmod(0o755)

    # node stub
    (bin_dir / "node").write_text("#!/bin/bash\nexit 0\n")
    (bin_dir / "node").chmod(0o755)

    return bin_dir


def run_install(tmp_path: Path, workspace: Path, bin_dir: Path,
                extra_env: dict | None = None, args: str = "") -> tuple[int, str, str]:
    """Run install.sh with stubbed commands and isolated workspace."""
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "ORCA_WORKSPACE": str(workspace),
        "TERM": "dumb",
    }
    if extra_env:
        env.update(extra_env)

    # Create fake HOME/.claude dir
    home_claude = tmp_path / "home" / ".claude" / "plugins"
    home_claude.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["bash", str(INSTALL_SH)] + (args.split() if args else []),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def get_claude_calls(tmp_path: Path) -> list[str]:
    """Read recorded claude CLI calls."""
    log = tmp_path / "claude_calls.log"
    if log.exists():
        return [l.strip() for l in log.read_text().splitlines() if l.strip()]
    return []


# ---------------------------------------------------------------------------
# Fresh install (none → v2)
# ---------------------------------------------------------------------------

class TestFreshInstall:
    """Validates fresh install creates all configs correctly."""

    def test_exits_0(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        code, _, _ = run_install(tmp_path, workspace, bin_dir)
        assert code == 0

    def test_creates_serena_configs(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        # Workspace root
        assert (workspace / ".serena" / "project.yml").exists()
        yml = (workspace / ".serena" / "project.yml").read_text()
        assert 'project_name: "orca-unified"' in yml

        # Individual repos
        for repo in ["orca", "orca-sensor", "orca-runtime-sensor"]:
            yml_path = workspace / repo / ".serena" / "project.yml"
            assert yml_path.exists(), f"Missing .serena/project.yml for {repo}"
            content = yml_path.read_text()
            assert f'project_name: "{repo}"' in content

    def test_creates_serena_gitignore(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        gi = workspace / ".serena" / ".gitignore"
        assert gi.exists()
        assert "cache/" in gi.read_text()

    def test_creates_cbmignore_files(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        # Workspace root
        assert (workspace / ".cbmignore").exists()
        root_ignore = (workspace / ".cbmignore").read_text()
        assert "/helm-charts/" in root_ignore

        # Individual repos
        for repo in ["orca", "orca-sensor", "orca-runtime-sensor"]:
            path = workspace / repo / ".cbmignore"
            assert path.exists(), f"Missing .cbmignore for {repo}"
            assert f"codebase-memory-mcp ignore" in path.read_text()

    def test_orca_cbmignore_excludes_heavy_dirs(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        content = (workspace / "orca" / ".cbmignore").read_text()
        for pattern in ["broots/", "**/migrations/", "*.json", "__pycache__/"]:
            assert pattern in content, f"Missing pattern '{pattern}' in orca .cbmignore"

    def test_runtime_sensor_cbmignore_excludes_python_env(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        content = (workspace / "orca-runtime-sensor" / ".cbmignore").read_text()
        assert "scripts/python/" in content

    def test_serena_config_languages(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        # orca should have python
        orca_yml = (workspace / "orca" / ".serena" / "project.yml").read_text()
        assert "python" in orca_yml

        # orca-sensor should have go, not python
        sensor_yml = (workspace / "orca-sensor" / ".serena" / "project.yml").read_text()
        assert "go" in sensor_yml

        # orca-runtime-sensor should have cpp
        rts_yml = (workspace / "orca-runtime-sensor" / ".serena" / "project.yml").read_text()
        assert "cpp" in rts_yml


# ---------------------------------------------------------------------------
# CLI usage — no direct file manipulation
# ---------------------------------------------------------------------------

class TestUsesCliCommands:
    """Verify install.sh uses claude CLI, not direct file writes, for managed configs."""

    def test_uses_claude_mcp_add(self, tmp_path):
        """MCP server must be added via `claude mcp add`, not .mcp.json write."""
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # Make claude mcp list return empty (no cbm configured)
        (bin_dir / "claude").write_text(textwrap.dedent(f"""\
            #!/bin/bash
            echo "$@" >> "{tmp_path}/claude_calls.log"
            case "$1 $2" in
                "plugin marketplace") echo "orca-sensor-marketplace" ;;
                "plugin list") echo "claude-toolkit@orca-sensor-marketplace  2.1.0  user" ;;
                "plugin update") echo "already latest" ;;
                "mcp list") echo "serena: http://127.0.0.1:8765/mcp" ;;
                "mcp add") echo "Added" ;;
            esac
            exit 0
        """))
        (bin_dir / "claude").chmod(0o755)

        run_install(tmp_path, workspace, bin_dir)
        calls = get_claude_calls(tmp_path)

        mcp_add_calls = [c for c in calls if c.startswith("mcp add")]
        assert len(mcp_add_calls) == 1, f"Expected 1 mcp add call, got: {mcp_add_calls}"
        assert "codebase-memory-mcp" in mcp_add_calls[0]
        assert "--scope project" in mcp_add_calls[0]

    def test_does_not_write_mcp_json(self, tmp_path):
        """install.sh must NOT create or modify .mcp.json directly."""
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        # .mcp.json should NOT be created by install.sh
        # (claude mcp add handles it)
        assert not (workspace / ".mcp.json").exists(), \
            "install.sh must not write .mcp.json directly — use claude mcp add"

    def test_does_not_write_settings_local_json(self, tmp_path):
        """install.sh must NOT create settings.local.json directly."""
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)
        run_install(tmp_path, workspace, bin_dir)

        assert not (workspace / ".claude" / "settings.local.json").exists(), \
            "install.sh must not write settings.local.json — claude mcp add handles server config"

    def test_uses_marketplace_add(self, tmp_path):
        """Marketplace must be added via claude CLI."""
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # Make marketplace list return empty
        (bin_dir / "claude").write_text(textwrap.dedent(f"""\
            #!/bin/bash
            echo "$@" >> "{tmp_path}/claude_calls.log"
            case "$1 $2" in
                "plugin marketplace")
                    case "$3" in
                        list) echo "" ;;
                        add) echo "Added" ;;
                    esac ;;
                "plugin list") echo "" ;;
                "plugin install") echo "Installed" ;;
                "mcp list") echo "codebase-memory-mcp: npx" ;;
            esac
            exit 0
        """))
        (bin_dir / "claude").chmod(0o755)

        run_install(tmp_path, workspace, bin_dir)
        calls = get_claude_calls(tmp_path)

        mp_add = [c for c in calls if "marketplace add" in c]
        assert len(mp_add) == 1
        assert "ilyabrykau-orca/orca-sensor-marketplace" in mp_add[0]


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Running install.sh twice should not overwrite existing configs."""

    def test_serena_not_overwritten(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # First run creates configs
        run_install(tmp_path, workspace, bin_dir)

        # Modify a config to detect overwrite
        marker = "# CUSTOM_MARKER_DO_NOT_OVERWRITE"
        yml = workspace / ".serena" / "project.yml"
        yml.write_text(yml.read_text() + f"\n{marker}\n")

        # Second run (without --force)
        run_install(tmp_path, workspace, bin_dir)

        assert marker in yml.read_text(), \
            "install.sh overwrote .serena/project.yml without --force"

    def test_cbmignore_not_overwritten(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        run_install(tmp_path, workspace, bin_dir)

        marker = "# MY_CUSTOM_RULE"
        ignore = workspace / ".cbmignore"
        ignore.write_text(ignore.read_text() + f"\n{marker}\n")

        run_install(tmp_path, workspace, bin_dir)

        assert marker in ignore.read_text(), \
            "install.sh overwrote .cbmignore without --force"

    def test_force_overwrites(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        run_install(tmp_path, workspace, bin_dir)

        marker = "# WILL_BE_GONE"
        yml = workspace / ".serena" / "project.yml"
        yml.write_text(marker)

        run_install(tmp_path, workspace, bin_dir, args="--force")

        assert marker not in yml.read_text(), \
            "--force should overwrite existing configs"


# ---------------------------------------------------------------------------
# Partial workspace (missing repos)
# ---------------------------------------------------------------------------

class TestPartialWorkspace:
    """Install should handle workspaces with only some repos."""

    def test_only_orca(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path, repos=["orca"])
        bin_dir = make_stub_bin(tmp_path)
        code, stdout, _ = run_install(tmp_path, workspace, bin_dir)

        assert code == 0
        assert (workspace / "orca" / ".serena" / "project.yml").exists()
        assert (workspace / "orca" / ".cbmignore").exists()
        assert not (workspace / "orca-sensor" / ".serena" / "project.yml").exists()
        assert not (workspace / "orca-runtime-sensor" / ".cbmignore").exists()

    def test_empty_workspace(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path, repos=[])
        bin_dir = make_stub_bin(tmp_path)
        code, _, _ = run_install(tmp_path, workspace, bin_dir)

        assert code == 0
        # Should still create workspace-level configs
        assert (workspace / ".serena" / "project.yml").exists()
        assert (workspace / ".cbmignore").exists()


# ---------------------------------------------------------------------------
# v1 → v2 migration
# ---------------------------------------------------------------------------

class TestV1Migration:
    """Detect and warn about Codanna leftovers."""

    def test_detects_codanna_directory(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # Create .codanna dir
        (workspace / "orca" / ".codanna").mkdir()

        code, stdout, _ = run_install(tmp_path, workspace, bin_dir)
        assert code == 0
        assert ".codanna" in stdout

    def test_detects_codanna_in_serena_memories(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # Create a Serena memory with Codanna reference
        mem_dir = workspace / ".serena" / "memories"
        mem_dir.mkdir(parents=True)
        (mem_dir / "old_tool_schemas.md").write_text("Use codanna for search")

        code, stdout, _ = run_install(tmp_path, workspace, bin_dir)
        assert code == 0
        assert "old_tool_schemas" in stdout or "codanna" in stdout.lower()

    def test_detects_codanna_mcp_server(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = make_stub_bin(tmp_path)

        # Make claude mcp list return codanna
        (bin_dir / "claude").write_text(textwrap.dedent(f"""\
            #!/bin/bash
            echo "$@" >> "{tmp_path}/claude_calls.log"
            case "$1 $2" in
                "plugin marketplace") echo "orca-sensor-marketplace" ;;
                "plugin list") echo "claude-toolkit@orca-sensor-marketplace  2.1.0  user" ;;
                "plugin update") echo "latest" ;;
                "mcp list") echo "codanna: https://localhost:8443/mcp
codebase-memory-mcp: npx -y codebase-memory-mcp" ;;
            esac
            exit 0
        """))
        (bin_dir / "claude").chmod(0o755)

        code, stdout, _ = run_install(tmp_path, workspace, bin_dir)
        assert code == 0
        assert "codanna" in stdout.lower() or "Codanna" in stdout


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

class TestPrerequisites:
    """Install must fail fast on missing prerequisites."""

    def test_fails_without_claude(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        # Only jq, no claude
        real_jq = subprocess.run(["which", "jq"], capture_output=True, text=True).stdout.strip()
        (bin_dir / "jq").write_text(f"#!/bin/bash\nexec {real_jq} \"$@\"\n")
        (bin_dir / "jq").chmod(0o755)

        code, _, _ = run_install(tmp_path, workspace, bin_dir)
        assert code != 0

    def test_fails_without_jq(self, tmp_path):
        workspace = setup_fake_workspace(tmp_path)
        bin_dir = tmp_path / "empty_bin"
        bin_dir.mkdir()
        # Only claude, no jq — use isolated PATH so system jq isn't found
        (bin_dir / "claude").write_text("#!/bin/bash\nexit 0\n")
        (bin_dir / "claude").chmod(0o755)
        (bin_dir / "bash").symlink_to("/bin/bash")
        (bin_dir / "echo").symlink_to("/bin/echo")

        env = {
            "PATH": str(bin_dir),
            "HOME": str(tmp_path / "home"),
            "ORCA_WORKSPACE": str(workspace),
            "TERM": "dumb",
        }
        (tmp_path / "home" / ".claude" / "plugins").mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            ["bash", str(INSTALL_SH)],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode != 0

    def test_fails_without_workspace(self, tmp_path):
        bin_dir = make_stub_bin(tmp_path)
        fake_ws = tmp_path / "nonexistent"

        code, _, _ = run_install(tmp_path, fake_ws, bin_dir)
        assert code != 0
