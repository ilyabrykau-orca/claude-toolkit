"""Tests for hooks/post-cbm-trace — tracks cbm calls for edit guard."""
import json
import subprocess
import os
from pathlib import Path

import pytest


class TestPostCbmTrace:
    """post-cbm-trace records traced files when cbm tools complete."""

    def test_records_trace_call_path(self, run_hook_isolated, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        rc, _, _ = run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__trace_call_path",
            "tool_input": {"from_symbol": "main", "to_symbol": "process"},
            "tool_response": {"content": [{"text": "found path"}]},
            "session_id": "test-sess",
        })
        assert rc == 0
        state_file = tmp_path / "state" / "refs-traced.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["session_id"] == "test-sess"
        assert "_session_traced" in state["traced"]

    def test_records_search_graph(self, run_hook_isolated, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        rc, _, _ = run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__search_graph",
            "tool_input": {"name_pattern": "MyClass"},
            "session_id": "test-sess",
        })
        assert rc == 0
        state = json.loads((tmp_path / "state" / "refs-traced.json").read_text())
        assert state["session_id"] == "test-sess"

    def test_ignores_unrelated_tools(self, run_hook_isolated, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        rc, _, _ = run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__get_architecture",
            "tool_input": {},
            "session_id": "test-sess",
        })
        assert rc == 0
        assert not (tmp_path / "state" / "refs-traced.json").exists()

    def test_ignores_errored_response(self, run_hook_isolated, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        rc, _, _ = run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__trace_call_path",
            "tool_input": {"from_symbol": "main"},
            "tool_response": {"is_error": True},
            "session_id": "test-sess",
        })
        assert rc == 0
        assert not (tmp_path / "state" / "refs-traced.json").exists()

    def test_session_change_resets_state(self, run_hook_isolated, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        # Session 1
        run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__search_graph",
            "tool_input": {"name_pattern": "old"},
            "session_id": "session-1",
        })
        # Session 2
        run_hook_isolated(hook, {
            "tool_name": "mcp__codebase-memory-mcp__search_graph",
            "tool_input": {"name_pattern": "new"},
            "session_id": "session-2",
        })
        state = json.loads((tmp_path / "state" / "refs-traced.json").read_text())
        assert state["session_id"] == "session-2"

    def test_always_exits_0_on_bad_input(self, plugin_root, tmp_path):
        hook = plugin_root / "hooks" / "post-cbm-trace"
        result = subprocess.run(
            ["bash", str(hook)],
            input="not json",
            capture_output=True, text=True, timeout=10,
            env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(tmp_path)},
        )
        assert result.returncode == 0
