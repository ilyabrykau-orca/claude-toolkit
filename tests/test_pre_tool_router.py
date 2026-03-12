"""Tests for hooks/pre-tool-router — verifies NEW cbm routing behavior (TDD red phase).

These tests are written against the EXPECTED post-migration behavior where:
- Layer 1: Grep/Glob blocked → suggest cbm search_graph / search_code
- Layer 2: Read on code files → suggest get_code_snippet or rtk read
- Layer 2: Edit/Write on code files → suggest mcp__serena__replace
- Layer 3: Serena edit without trace → warn (exit 1), with trace → allow (exit 0)

Tests WILL FAIL against the current hook (which still references Codanna/Serena).
That is expected — this is the TDD "red" phase.
"""
import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = PLUGIN_ROOT / "hooks" / "pre-tool-router"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CODE_EXTENSIONS = [
    ".py", ".go", ".ts", ".tsx", ".js", ".jsx",
    ".rs", ".java", ".cpp", ".c", ".h", ".rb", ".sh",
]

NON_CODE_FILES = [
    "config.yaml",
    "README.md",
    "settings.json",
    ".gitignore",
    "Makefile",
    "Dockerfile",
    "pyproject.toml",
]

SERENA_EDIT_TOOLS = [
    "mcp__serena__replace_symbol_body",
    "mcp__serena__replace_content",
    "mcp__serena__insert_after_symbol",
    "mcp__serena__insert_before_symbol",
    "mcp__serena__rename_symbol",
]


def make_tool_input(tool_name, file_path=None, pattern=None, relative_path=None, session_id=None):
    """Build minimal hook input JSON."""
    tool_input = {}
    if file_path is not None:
        tool_input["file_path"] = file_path
    if pattern is not None:
        tool_input["pattern"] = pattern
    if relative_path is not None:
        tool_input["relative_path"] = relative_path

    payload = {"tool_name": tool_name, "tool_input": tool_input}
    if session_id is not None:
        payload["session_id"] = session_id
    return payload


# ---------------------------------------------------------------------------
# Layer 1: Block Grep / Glob
# ---------------------------------------------------------------------------

class TestLayer1BlockGrepGlob:
    """Grep and Glob must be blocked unconditionally with cbm suggestions."""

    def test_grep_blocked_exit_code(self, run_hook):
        code, _, _ = run_hook("pre-tool-router", make_tool_input("Grep", pattern="TODO"))
        assert code == 2

    def test_grep_blocked_message_contains_blocked(self, run_hook):
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Grep", pattern="TODO"))
        assert "BLOCKED" in stderr

    def test_grep_suggests_cbm_search_code(self, run_hook):
        """Grep block message should suggest cbm search_code tool."""
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Grep", pattern="TODO"))
        assert "search_code" in stderr or "search_graph" in stderr

    def test_grep_suggests_search_graph(self, run_hook):
        """Grep block message should mention search_graph as an alternative."""
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Grep", pattern="foo"))
        assert "search_graph" in stderr or "search_code" in stderr

    def test_glob_blocked_exit_code(self, run_hook):
        code, _, _ = run_hook("pre-tool-router", make_tool_input("Glob", pattern="**/*.py"))
        assert code == 2

    def test_glob_blocked_message_contains_blocked(self, run_hook):
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Glob", pattern="**/*.py"))
        assert "BLOCKED" in stderr

    def test_glob_suggests_cbm_search_graph(self, run_hook):
        """Glob block message should suggest cbm search_graph tool."""
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Glob", pattern="**/*.go"))
        assert "search_graph" in stderr

    def test_grep_no_codanna_reference(self, run_hook):
        """Post-migration, Grep block should NOT reference Codanna."""
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Grep", pattern="bar"))
        assert "codanna" not in stderr.lower()

    def test_glob_no_codanna_reference(self, run_hook):
        """Post-migration, Glob block should NOT reference Codanna."""
        _, _, stderr = run_hook("pre-tool-router", make_tool_input("Glob", pattern="**/*.ts"))
        assert "codanna" not in stderr.lower()


# ---------------------------------------------------------------------------
# Layer 2: Block Read/Edit/Write on code files
# ---------------------------------------------------------------------------

class TestLayer2BlockCodeFiles:
    """Read/Edit/Write on code files must be blocked with cbm suggestions."""

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_read_blocked_on_code_file(self, run_hook, ext):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Read", file_path=f"src/main{ext}"),
        )
        assert code == 2

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_read_blocked_message(self, run_hook, ext):
        _, _, stderr = run_hook(
            "pre-tool-router",
            make_tool_input("Read", file_path=f"src/main{ext}"),
        )
        assert "BLOCKED" in stderr

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_read_suggests_get_code_snippet(self, run_hook, ext):
        """Read block should suggest cbm get_code_snippet or rtk read."""
        _, _, stderr = run_hook(
            "pre-tool-router",
            make_tool_input("Read", file_path=f"app/module{ext}"),
        )
        assert "get_code_snippet" in stderr or "rtk read" in stderr

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_read_no_serena_find_symbol_reference(self, run_hook, ext):
        """Post-migration, Read block should NOT reference mcp__serena__find_symbol."""
        _, _, stderr = run_hook(
            "pre-tool-router",
            make_tool_input("Read", file_path=f"app/module{ext}"),
        )
        assert "mcp__serena__find_symbol" not in stderr
        assert "mcp__serena__read_file" not in stderr

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_edit_blocked_on_code_file(self, run_hook, ext):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Edit", file_path=f"src/module{ext}"),
        )
        assert code == 2

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_edit_suggests_serena_replace(self, run_hook, ext):
        """Edit block should suggest mcp__serena__replace (stays Serena post-migration)."""
        _, _, stderr = run_hook(
            "pre-tool-router",
            make_tool_input("Edit", file_path=f"src/module{ext}"),
        )
        assert "mcp__serena__replace" in stderr

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_write_blocked_on_code_file(self, run_hook, ext):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Write", file_path=f"src/module{ext}"),
        )
        assert code == 2

    @pytest.mark.parametrize("ext", CODE_EXTENSIONS)
    def test_write_suggests_serena_replace(self, run_hook, ext):
        """Write block should suggest mcp__serena__replace."""
        _, _, stderr = run_hook(
            "pre-tool-router",
            make_tool_input("Write", file_path=f"src/module{ext}"),
        )
        assert "mcp__serena__replace" in stderr


# ---------------------------------------------------------------------------
# Layer 2: Allow non-code files and Bash
# ---------------------------------------------------------------------------

class TestLayer2AllowNonCode:
    """Read on non-code files must be allowed (exit 0). Bash always allowed."""

    @pytest.mark.parametrize("filename", NON_CODE_FILES)
    def test_read_allowed_on_non_code(self, run_hook, filename):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Read", file_path=filename),
        )
        assert code == 0

    @pytest.mark.parametrize("filename", NON_CODE_FILES)
    def test_edit_allowed_on_non_code(self, run_hook, filename):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Edit", file_path=filename),
        )
        assert code == 0

    @pytest.mark.parametrize("filename", NON_CODE_FILES)
    def test_write_allowed_on_non_code(self, run_hook, filename):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Write", file_path=filename),
        )
        assert code == 0

    def test_bash_always_allowed(self, run_hook):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("Bash"),
        )
        assert code == 0

    def test_bash_with_command_allowed(self, run_hook):
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }
        code, _, _ = run_hook("pre-tool-router", payload)
        assert code == 0


# ---------------------------------------------------------------------------
# Layer 3: Serena edit guard
# ---------------------------------------------------------------------------

class TestLayer3EditGuard:
    """Serena edit tools require prior find_referencing_symbols trace."""

    @pytest.mark.parametrize("tool_name", SERENA_EDIT_TOOLS)
    def test_edit_without_trace_warns(self, run_hook_isolated, tmp_path, tool_name):
        """Editing without a state file should exit 1 (warn)."""
        code, _, _ = run_hook_isolated(
            HOOK_PATH,
            make_tool_input(tool_name, relative_path="src/foo.py", session_id="sess-abc"),
            plugin_root_override=tmp_path,
        )
        assert code == 1

    @pytest.mark.parametrize("tool_name", SERENA_EDIT_TOOLS)
    def test_edit_without_trace_mentions_cbm(self, run_hook_isolated, tmp_path, tool_name):
        """Warn message should suggest cbm trace_call_path or search_graph."""
        _, _, stderr = run_hook_isolated(
            HOOK_PATH,
            make_tool_input(tool_name, relative_path="src/foo.py", session_id="sess-abc"),
            plugin_root_override=tmp_path,
        )
        assert "trace_call_path" in stderr or "search_graph" in stderr

    @pytest.mark.parametrize("tool_name", SERENA_EDIT_TOOLS)
    def test_edit_with_trace_allowed(self, run_hook_isolated, tmp_path, tool_name):
        """Editing after tracing (state file present, same session) should exit 0."""
        session_id = "sess-xyz"
        relative_path = "src/bar.py"

        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "refs-traced.json"
        state_file.write_text(
            json.dumps({"session_id": session_id, "traced": {relative_path: True}})
        )

        code, _, _ = run_hook_isolated(
            HOOK_PATH,
            make_tool_input(tool_name, relative_path=relative_path, session_id=session_id),
            plugin_root_override=tmp_path,
        )
        assert code == 0

    @pytest.mark.parametrize("tool_name", SERENA_EDIT_TOOLS)
    def test_edit_with_different_session_warns(self, run_hook_isolated, tmp_path, tool_name):
        """State file for a different session should still warn (exit 1)."""
        relative_path = "src/baz.py"

        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "refs-traced.json"
        state_file.write_text(
            json.dumps({"session_id": "old-session", "traced": {relative_path: True}})
        )

        code, _, _ = run_hook_isolated(
            HOOK_PATH,
            make_tool_input(tool_name, relative_path=relative_path, session_id="new-session"),
            plugin_root_override=tmp_path,
        )
        assert code == 1

    @pytest.mark.parametrize("tool_name", SERENA_EDIT_TOOLS)
    def test_edit_with_missing_path_in_state_warns(self, run_hook_isolated, tmp_path, tool_name):
        """State file present but path not traced should warn (exit 1)."""
        session_id = "sess-123"

        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "refs-traced.json"
        state_file.write_text(
            json.dumps({"session_id": session_id, "traced": {"src/other.py": True}})
        )

        code, _, _ = run_hook_isolated(
            HOOK_PATH,
            make_tool_input(tool_name, relative_path="src/untraced.py", session_id=session_id),
            plugin_root_override=tmp_path,
        )
        assert code == 1

    def test_all_five_serena_edit_tools_guarded(self, run_hook_isolated, tmp_path):
        """Verify all 5 Serena edit tools trigger the guard (exit 1 without trace)."""
        results = {}
        for tool_name in SERENA_EDIT_TOOLS:
            code, _, _ = run_hook_isolated(
                HOOK_PATH,
                make_tool_input(tool_name, relative_path="lib/mod.py", session_id="s1"),
                plugin_root_override=tmp_path,
            )
            results[tool_name] = code

        failing = [t for t, c in results.items() if c != 1]
        assert failing == [], f"These tools did not warn (exit 1): {failing}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Hook must fail-open on malformed or missing input."""

    def test_empty_json_exits_0(self, run_hook):
        code, _, _ = run_hook("pre-tool-router", {})
        assert code == 0

    def test_unknown_tool_exits_0(self, run_hook):
        code, _, _ = run_hook(
            "pre-tool-router",
            make_tool_input("SomeUnknownTool"),
        )
        assert code == 0

    def test_read_without_file_path_exits_0(self, run_hook):
        """Read with no file_path should not be blocked."""
        code, _, _ = run_hook(
            "pre-tool-router",
            {"tool_name": "Read", "tool_input": {}},
        )
        assert code == 0

    def test_serena_edit_without_relative_path_exits_0(self, run_hook_isolated, tmp_path):
        """Serena edit without relative_path should not trigger the guard."""
        code, _, _ = run_hook_isolated(
            HOOK_PATH,
            {"tool_name": "mcp__serena__replace_content", "tool_input": {}, "session_id": "s1"},
            plugin_root_override=tmp_path,
        )
        assert code == 0
