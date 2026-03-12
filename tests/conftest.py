"""Shared fixtures for claude-toolkit plugin tests."""
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def plugin_root():
    """Absolute path to the plugin root directory."""
    return PLUGIN_ROOT


@pytest.fixture
def run_hook(plugin_root):
    """Run a hook script with JSON on stdin, return (exit_code, stdout, stderr)."""

    def _run(hook_name: str, input_data: dict, env_overrides: dict | None = None):
        hook_path = plugin_root / "hooks" / hook_name
        env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
        if env_overrides:
            env.update(env_overrides)

        result = subprocess.run(
            ["bash", str(hook_path)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    return _run


@pytest.fixture
def run_hook_isolated(tmp_path):
    """Run a hook with an isolated CLAUDE_PLUGIN_ROOT (for state file tests)."""

    def _run(hook_path, input_data: dict, plugin_root_override=None):
        env = {
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(plugin_root_override or tmp_path),
        }
        result = subprocess.run(
            ["bash", str(hook_path)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr

    return _run


@pytest.fixture
def refs_state(tmp_path):
    """Helper to read/write refs-traced.json state files."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "refs-traced.json"

    class RefsState:
        path = state_file
        dir = state_dir

        def write(self, session_id: str, traced: dict):
            state_file.write_text(json.dumps({"session_id": session_id, "traced": traced}))

        def read(self):
            if state_file.exists():
                return json.loads(state_file.read_text())
            return None

        def clear(self):
            if state_file.exists():
                state_file.unlink()

    return RefsState()


@pytest.fixture
def tmp_project(tmp_path):
    """Isolated project dir with .claude.json, settings.json, LaunchAgents/."""
    claude_json = tmp_path / ".claude.json"
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    settings_json = settings_dir / "settings.json"
    launch_agents = tmp_path / "LaunchAgents"
    launch_agents.mkdir()

    class Project:
        root = tmp_path
        claude_json_path = claude_json
        settings_json_path = settings_json
        launch_agents_path = launch_agents

    return Project()
