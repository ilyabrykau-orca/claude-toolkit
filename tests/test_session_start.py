"""Tests for hooks/session-start — validates the full startup pipeline.

Covers:
- Valid JSON output structure (additionalContext + additional_context)
- Project detection from $PWD
- Skill content injection (orca-setup SKILL.md)
- Memory instruction uses codebase-memory-mcp (NOT Serena list_memories)
- CBM project routing injection
- EXTREMELY_IMPORTANT wrapper
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = PLUGIN_ROOT / "hooks" / "session-start"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_session_start(cwd: str, plugin_root: Path = PLUGIN_ROOT) -> tuple[int, dict | None, str]:
    """Run session-start hook with a given $PWD, return (exit_code, parsed_json, stderr)."""
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": str(plugin_root),
        "PWD": cwd,
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    result = subprocess.run(
        ["bash", str(HOOK_PATH)],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        cwd=cwd if Path(cwd).exists() else "/tmp",
    )
    parsed = None
    if result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
    return result.returncode, parsed, result.stderr


def get_context(parsed: dict) -> str:
    """Extract the additional_context string from parsed JSON."""
    return parsed.get("additional_context", "")


# ---------------------------------------------------------------------------
# JSON output structure
# ---------------------------------------------------------------------------

class TestJsonOutput:
    """session-start must produce valid dual-shape JSON."""

    def test_exits_0(self):
        code, _, _ = run_session_start("/tmp")
        assert code == 0

    def test_produces_valid_json(self):
        _, parsed, _ = run_session_start("/tmp")
        assert parsed is not None, "session-start must produce valid JSON on stdout"

    def test_has_additional_context_key(self):
        _, parsed, _ = run_session_start("/tmp")
        assert "additional_context" in parsed

    def test_has_hook_specific_output(self):
        _, parsed, _ = run_session_start("/tmp")
        assert "hookSpecificOutput" in parsed
        hso = parsed["hookSpecificOutput"]
        assert hso["hookEventName"] == "SessionStart"
        assert "additionalContext" in hso

    def test_both_contexts_match(self):
        """additional_context and hookSpecificOutput.additionalContext must be identical."""
        _, parsed, _ = run_session_start("/tmp")
        assert parsed["additional_context"] == parsed["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

PROJECT_CASES = [
    ("/Users/ilyabrykau/src", "orca-unified"),
    ("/Users/ilyabrykau/src/orca", "orca"),
    ("/Users/ilyabrykau/src/orca-sensor", "orca-sensor"),
    ("/Users/ilyabrykau/src/orca-runtime-sensor", "orca-runtime-sensor"),
    ("/Users/ilyabrykau/src/helm-charts", "helm-charts"),
]

NO_PROJECT_CASES = [
    "/tmp",
    "/Users/ilyabrykau",
    "/Users/ilyabrykau/src/orca-cloud-platform",
]


class TestProjectDetection:
    """Verifies detect_project() produces correct project names."""

    @pytest.mark.parametrize("cwd,expected_project", PROJECT_CASES)
    def test_detected_project(self, cwd, expected_project):
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert f"project='{expected_project}'" in ctx or f"project={expected_project}" in ctx

    @pytest.mark.parametrize("cwd", NO_PROJECT_CASES)
    def test_no_project_detected(self, cwd):
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert "SERENA WORKSPACE DETECTED" not in ctx

    @pytest.mark.parametrize("cwd,expected_project", PROJECT_CASES)
    def test_activate_project_instruction(self, cwd, expected_project):
        """When project is detected, must instruct to call activate_project."""
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert f"mcp__serena__activate_project(project={expected_project})" in ctx


# ---------------------------------------------------------------------------
# Memory instructions — the critical fix
# ---------------------------------------------------------------------------

class TestMemoryInstructions:
    """Memory flow must use codebase-memory-mcp manage_adr, NOT Serena memories."""

    @pytest.mark.parametrize("cwd,_", PROJECT_CASES)
    def test_no_serena_list_memories(self, cwd, _):
        """session-start must NOT tell Claude to use mcp__serena__list_memories."""
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert "list_memories" not in ctx, (
            "Found 'list_memories' in session context — must use manage_adr instead"
        )

    @pytest.mark.parametrize("cwd,_", PROJECT_CASES)
    def test_no_serena_read_memory(self, cwd, _):
        """session-start must NOT reference mcp__serena__read_memory."""
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert "read_memory" not in ctx
        assert "write_memory" not in ctx
        assert "delete_memory" not in ctx
        assert "edit_memory" not in ctx

    @pytest.mark.parametrize("cwd,_", PROJECT_CASES)
    def test_uses_cbm_manage_adr(self, cwd, _):
        """session-start must instruct Claude to use codebase-memory-mcp manage_adr."""
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert "manage_adr" in ctx, (
            "session context must reference manage_adr for memory operations"
        )

    @pytest.mark.parametrize("cwd,_", PROJECT_CASES)
    def test_memory_instruction_in_project_block(self, cwd, _):
        """The 'Then:' instruction after activate_project must use manage_adr."""
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        lines = ctx.split("\n")
        then_lines = [l for l in lines if l.strip().startswith("Then:")]
        assert len(then_lines) >= 1, "Must have a 'Then:' instruction"
        for line in then_lines:
            assert "manage_adr" in line, (
                f"'Then:' instruction must reference manage_adr, got: {line}"
            )
            assert "list_memories" not in line, (
                f"'Then:' instruction must NOT reference list_memories, got: {line}"
            )


# ---------------------------------------------------------------------------
# Skill content injection
# ---------------------------------------------------------------------------

class TestSkillContentInjection:
    """session-start must inject the orca-setup SKILL.md content."""

    def test_contains_extremely_important_wrapper(self):
        _, parsed, _ = run_session_start("/Users/ilyabrykau/src")
        ctx = get_context(parsed)
        assert "<EXTREMELY_IMPORTANT>" in ctx
        assert "</EXTREMELY_IMPORTANT>" in ctx

    def test_contains_tool_enforcement_section(self):
        _, parsed, _ = run_session_start("/Users/ilyabrykau/src")
        ctx = get_context(parsed)
        assert "TOOL ENFORCEMENT ACTIVE" in ctx

    def test_contains_edit_tools_section(self):
        _, parsed, _ = run_session_start("/Users/ilyabrykau/src")
        ctx = get_context(parsed)
        assert "replace_symbol_body" in ctx

    def test_contains_params_cheat_sheet(self):
        _, parsed, _ = run_session_start("/Users/ilyabrykau/src")
        ctx = get_context(parsed)
        assert "Params Cheat Sheet" in ctx

    def test_contains_memory_protocol_section(self):
        """The skill's Step 3: Memory Protocol must be present."""
        _, parsed, _ = run_session_start("/Users/ilyabrykau/src")
        ctx = get_context(parsed)
        assert "Memory Protocol" in ctx
        assert "manage_adr" in ctx


# ---------------------------------------------------------------------------
# CBM project routing
# ---------------------------------------------------------------------------

CBM_PROJECT_CASES = [
    ("/Users/ilyabrykau/src", "Users-ilyabrykau-src"),
    ("/Users/ilyabrykau/src/orca", "Users-ilyabrykau-src-orca"),
    ("/Users/ilyabrykau/src/orca-sensor", "Users-ilyabrykau-src-orca-sensor"),
    ("/Users/ilyabrykau/src/orca-runtime-sensor", "Users-ilyabrykau-src-orca-runtime-sensor"),
]


class TestCbmProjectRouting:
    """CBM project routing context must be injected for known workspaces."""

    @pytest.mark.parametrize("cwd,expected_cbm", CBM_PROJECT_CASES)
    def test_cbm_default_project(self, cwd, expected_cbm):
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert expected_cbm in ctx, (
            f"CBM project '{expected_cbm}' must appear in context for cwd={cwd}"
        )

    @pytest.mark.parametrize("cwd,_", CBM_PROJECT_CASES)
    def test_cbm_routing_section_present(self, cwd, _):
        _, parsed, _ = run_session_start(cwd)
        ctx = get_context(parsed)
        assert "CBM PROJECT ROUTING" in ctx

    def test_no_cbm_routing_for_unknown_path(self):
        _, parsed, _ = run_session_start("/tmp")
        ctx = get_context(parsed)
        assert "CBM PROJECT ROUTING" not in ctx


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Hook must be resilient to missing skill file or unusual paths."""

    def test_missing_skill_file_still_exits_0(self, tmp_path):
        """If SKILL.md doesn't exist, hook should still produce valid JSON."""
        hooks_dir = tmp_path / "hooks"
        hooks_dir.mkdir()
        import shutil
        shutil.copy(HOOK_PATH, hooks_dir / "session-start")

        code, parsed, _ = run_session_start("/tmp", plugin_root=tmp_path)
        assert code == 0
        assert parsed is not None

    def test_non_orca_path_produces_minimal_context(self):
        """For paths outside orca workspace, still get skill content but no project block."""
        _, parsed, _ = run_session_start("/tmp")
        ctx = get_context(parsed)
        assert "<EXTREMELY_IMPORTANT>" in ctx
        assert "SERENA WORKSPACE DETECTED" not in ctx
